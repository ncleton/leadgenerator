"""Guarded Enrow and FullEnrich clients for professional contact lookups."""

from __future__ import annotations

import json
import os
from hashlib import sha256
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Provider = Literal["enrow", "fullenrich"]
EnrichmentField = Literal["work_email", "phone"]
EnrichmentStatus = Literal[
    "pending",
    "finished",
    "not_found",
    "failed",
    "canceled",
    "insufficient_credits",
    "rate_limited",
    "unknown",
]
API_KEYS = {"enrow": "ENROW_API_KEY", "fullenrich": "FULLENRICH_API_KEY"}
ENROW_BASE = "https://api.enrow.io"
FULLENRICH_BASE = "https://app.fullenrich.com/api/v2/contact/enrich/bulk"


class StrictModel(BaseModel):
    """Reject undeclared enrichment data."""

    model_config = ConfigDict(extra="forbid")


class ContactLookup(StrictModel):
    """Minimum professional identity transmitted to an enrichment provider."""

    first_name: str
    last_name: str
    company_name: str | None = None
    company_domain: str | None = None
    linkedin_url: str | None = None
    identity_verified: bool = False
    identity_source_url: str | None = None
    fields: list[EnrichmentField] = Field(default_factory=lambda: ["work_email"])

    @model_validator(mode="after")
    def validate_identity(self) -> ContactLookup:
        """Require enough identity to avoid charging an ambiguous lookup."""
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        self.company_name = self.company_name.strip() if self.company_name else None
        self.linkedin_url = self.linkedin_url.strip() if self.linkedin_url else None
        self.identity_source_url = (
            self.identity_source_url.strip() if self.identity_source_url else None
        )
        if not self.first_name or not self.last_name:
            raise ValueError("Le prénom et le nom du contact sont requis.")
        if not any((self.company_name, self.company_domain, self.linkedin_url)):
            raise ValueError(
                "L'entreprise, son domaine ou le profil LinkedIn est requis."
            )
        if not self.fields:
            raise ValueError("Au moins un champ d'enrichissement est requis.")
        self.fields = list(dict.fromkeys(self.fields))
        if self.company_domain:
            parsed = urlparse(
                self.company_domain
                if "://" in self.company_domain
                else f"https://{self.company_domain}"
            )
            if not parsed.hostname:
                raise ValueError("Le domaine de l'entreprise est invalide.")
            self.company_domain = parsed.hostname.removeprefix("www.")
        if self.linkedin_url:
            parsed = urlparse(self.linkedin_url)
            hostname = str(parsed.hostname or "").lower()
            if (
                parsed.scheme != "https"
                or not (
                    hostname == "linkedin.com" or hostname.endswith(".linkedin.com")
                )
                or not parsed.path.startswith("/in/")
            ):
                raise ValueError(
                    "L'URL LinkedIn professionnelle du contact est invalide."
                )
        if self.identity_verified and not self.identity_source_url:
            raise ValueError(
                "Une source publique de vérification d'identité est requise."
            )
        if self.identity_source_url:
            source = urlparse(self.identity_source_url)
            if source.scheme not in {"http", "https"} or not source.hostname:
                raise ValueError("La source publique de l'identité est invalide.")
        return self


class EnrichmentJob(StrictModel):
    """Asynchronous provider job created after explicit confirmation."""

    provider: Provider
    job_id: str
    field: EnrichmentField | None = None
    status: str = "submitted"
    credits_used: float | None = None

    @field_validator("job_id")
    @classmethod
    def job_id_is_present(_cls, value: str) -> str:
        """Reject provider acknowledgements that cannot be polled safely."""
        normalized = value.strip()
        if not normalized:
            raise ValueError(
                "Le fournisseur n'a pas renvoyé d'identifiant de recherche."
            )
        return normalized


class EnrichedEmail(StrictModel):
    """One work email with FullEnrich's deliverability verdict."""

    email: str
    status: str


class EnrichedPhone(StrictModel):
    """One phone candidate with the available quality signals."""

    number: str
    region: str | None = None
    line_type: str | None = None
    line_status: str | None = None
    ownership_match: str | None = None
    ownership_match_confidence: int | None = None
    connect_rate: str | None = None


class CurrentEmployment(StrictModel):
    """Normalized current professional role returned by FullEnrich."""

    title: str | None = None
    seniority: str | None = None
    start_at: str | None = None
    is_current: bool = True
    company_name: str | None = None
    company_domain: str | None = None
    company_website: str | None = None
    company_linkedin_url: str | None = None
    company_logo_url: str | None = None


class EnrichmentResult(StrictModel):
    """Normalized provider response with provenance."""

    provider: Provider
    job_id: str
    status: EnrichmentStatus
    work_emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    work_email_details: list[EnrichedEmail] = Field(default_factory=list)
    phone_details: list[EnrichedPhone] = Field(default_factory=list)
    current_employment: CurrentEmployment | None = None
    professional_profile_url: str | None = None
    credits_used: float | None = None
    raw_qualification: str | None = None

    @property
    def terminal(self) -> bool:
        """Whether polling this provider job is complete."""
        return self.status in {
            "finished",
            "not_found",
            "failed",
            "canceled",
            "insufficient_credits",
        }


class EnrichmentCascadeState(StrictModel):
    """Auditable state for an Enrow-first, confirmed FullEnrich fallback."""

    contact_fingerprint: str
    requested_fields: list[EnrichmentField]
    enrow_job_ids: dict[EnrichmentField, str] = Field(default_factory=dict)
    enrow_results: dict[EnrichmentField, EnrichmentResult] = Field(default_factory=dict)
    fallback_confirmed_fields: list[EnrichmentField] = Field(default_factory=list)
    fullenrich_job_id: str | None = None

    @property
    def enrow_terminal(self) -> bool:
        """Whether Enrow has returned a terminal result for every requested field."""
        return bool(self.requested_fields) and all(
            field in self.enrow_results and self.enrow_results[field].terminal
            for field in self.requested_fields
        )

    @property
    def terminal_misses(self) -> list[EnrichmentField]:
        """Fields that Enrow conclusively did not return."""
        if not self.enrow_terminal:
            return []
        missing = []
        for field in self.requested_fields:
            result = self.enrow_results[field]
            values = result.work_emails if field == "work_email" else result.phones
            if result.status in {"finished", "not_found"} and not values:
                missing.append(field)
        return missing


class EnrichmentPlan(StrictModel):
    """Non-spending provider order for one requested lookup."""

    providers: list[Provider]
    rationale: str
    fallback_condition: str
    missing_configuration: list[str] = Field(default_factory=list)


def plan_contact_enrichment() -> EnrichmentPlan:
    """Plan the Enrow-to-FullEnrich cascade without calling either provider."""
    configured = {
        provider: bool(os.environ.get(env_name, "").strip())
        for provider, env_name in API_KEYS.items()
    }
    providers: list[Provider] = []
    if configured["enrow"]:
        providers.append("enrow")
    if configured["fullenrich"]:
        providers.append("fullenrich")
    missing = [
        API_KEYS[provider]
        for provider in ("enrow", "fullenrich")
        if not configured[provider]
    ]
    return EnrichmentPlan(
        providers=providers,
        rationale=(
            "Enrow passe en premier lorsqu'il est connecté car il est moins cher. "
            "FullEnrich est le recours recommandé pour maximiser la couverture et "
            "chercher un mobile."
        ),
        fallback_condition=(
            "N'appeler FullEnrich qu'après un résultat Enrow terminé sans la "
            "donnée demandée, et seulement si la confirmation humaine couvrait "
            "explicitement ce second appel payant."
        ),
        missing_configuration=missing,
    )


def _contact_fingerprint(contact: ContactLookup) -> str:
    """Bind cascade evidence to one normalized professional identity."""
    identity = {
        "first_name": contact.first_name.casefold(),
        "last_name": contact.last_name.casefold(),
        "company_name": (contact.company_name or "").casefold(),
        "company_domain": contact.company_domain or "",
        "linkedin_url": contact.linkedin_url or "",
        "identity_source_url": contact.identity_source_url or "",
    }
    return sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def create_enrichment_cascade(contact: ContactLookup) -> EnrichmentCascadeState:
    """Create a non-spending Enrow-first state bound to this verified contact."""
    return EnrichmentCascadeState(
        contact_fingerprint=_contact_fingerprint(contact),
        requested_fields=list(contact.fields),
    )


def confirm_fullenrich_fallback(
    state: EnrichmentCascadeState,
    *,
    fields: list[EnrichmentField] | None = None,
    confirmed: bool = False,
) -> EnrichmentCascadeState:
    """Record consent for exact terminal Enrow misses without spending credits."""
    _require_confirmation(confirmed)
    if not state.enrow_terminal:
        raise ValueError("Enrow doit être terminé avant de confirmer le recours.")
    selected = list(dict.fromkeys(fields or state.terminal_misses))
    if not selected or not set(selected) <= set(state.terminal_misses):
        raise ValueError(
            "La confirmation FullEnrich doit viser uniquement des champs manquants "
            "après la fin d'Enrow."
        )
    state.fallback_confirmed_fields = selected
    return state


def _api_key(provider: Provider) -> str:
    """Load a credential from the environment without ever returning its value."""
    env_name = API_KEYS[provider]
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise RuntimeError(
            f"{env_name} n'est pas configurée. Enregistrez la clé dans "
            "l'environnement local, jamais dans un skill ou dans le chat."
        )
    return value


def _request_json(
    url: str,
    *,
    method: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Call one fixed provider endpoint and return its JSON response."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 fixed URLs
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            f"{urlparse(url).hostname}: HTTP {exc.code}: {detail}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            f"Le fournisseur {urlparse(url).hostname} est inaccessible."
        ) from exc


def _require_confirmation(confirmed: bool) -> None:
    """Block paid transmission unless the user confirmed this exact lookup."""
    if not confirmed:
        raise PermissionError(
            "Confirmation requise juste avant l'appel : cette recherche transmet "
            "l'identité professionnelle à un fournisseur et peut consommer des crédits."
        )


def _require_verified_identity(contact: ContactLookup) -> None:
    """Keep unreviewed hypotheses away from paid enrichment providers."""
    if not contact.identity_verified or not contact.identity_source_url:
        raise ValueError(
            "L'identité professionnelle et sa source publique doivent être "
            "vérifiées avant enrichissement."
        )


def submit_contact_lookup(
    provider: Provider,
    contact: ContactLookup,
    *,
    confirmed: bool = False,
    cascade_state: EnrichmentCascadeState | None = None,
    timeout: int = 30,
) -> list[EnrichmentJob]:
    """Submit a paid asynchronous lookup after explicit human confirmation."""
    _require_confirmation(confirmed)
    _require_verified_identity(contact)
    if cascade_state is not None:
        if cascade_state.contact_fingerprint != _contact_fingerprint(contact):
            raise ValueError("L'état de cascade appartient à un autre contact.")
        if not set(contact.fields) <= set(cascade_state.requested_fields):
            raise ValueError("La cascade ne couvre pas tous les champs demandés.")
    if provider == "enrow":
        if "phone" in contact.fields and not contact.linkedin_url:
            raise ValueError(
                "Lead Studio exige un profil LinkedIn vérifié pour Enrow Phone."
            )
        key = _api_key(provider)
        jobs = _submit_enrow(contact, key=key, timeout=timeout)
        if cascade_state is not None:
            cascade_state.enrow_job_ids.update(
                {job.field: job.job_id for job in jobs if job.field is not None}
            )
        return jobs
    if cascade_state is None:
        raise PermissionError(
            "FullEnrich est un recours : fournissez l'état de cascade Enrow terminé."
        )
    if not cascade_state.enrow_terminal:
        raise PermissionError("FullEnrich est bloqué tant qu'Enrow n'est pas terminé.")
    requested = set(contact.fields)
    if not requested <= set(cascade_state.terminal_misses):
        raise PermissionError(
            "FullEnrich ne peut rechercher que les champs conclus manquants par Enrow."
        )
    if not requested <= set(cascade_state.fallback_confirmed_fields):
        raise PermissionError(
            "La confirmation humaine ne couvre pas ce recours FullEnrich payant."
        )
    key = _api_key(provider)
    job = _submit_fullenrich(contact, key=key, timeout=timeout)
    cascade_state.fullenrich_job_id = job.job_id
    return [job]


def _submit_enrow(
    contact: ContactLookup, *, key: str, timeout: int
) -> list[EnrichmentJob]:
    """Submit one Enrow job per requested field."""
    jobs = []
    headers = {"Content-Type": "application/json", "x-api-key": key}
    full_name = f"{contact.first_name.strip()} {contact.last_name.strip()}"
    for field in dict.fromkeys(contact.fields):
        if field == "work_email":
            endpoint = f"{ENROW_BASE}/email/find/single"
            payload: dict[str, Any] = {"fullname": full_name}
            if contact.company_domain:
                payload["company_domain"] = contact.company_domain
            elif contact.company_name:
                payload["company_name"] = contact.company_name
            else:
                raise ValueError("Enrow exige une entreprise pour chercher un email.")
        else:
            endpoint = f"{ENROW_BASE}/phone/single"
            if not contact.linkedin_url:
                raise ValueError(
                    "Lead Studio exige un profil LinkedIn vérifié pour Enrow Phone."
                )
            payload = {"linkedin_url": contact.linkedin_url}
        response = _request_json(
            endpoint,
            method="POST",
            headers=headers,
            payload=payload,
            timeout=timeout,
        )
        jobs.append(
            EnrichmentJob(
                provider="enrow",
                job_id=str(response.get("id") or ""),
                field=field,
                credits_used=response.get("credits_used"),
            )
        )
    return jobs


def _submit_fullenrich(
    contact: ContactLookup, *, key: str, timeout: int
) -> EnrichmentJob:
    """Submit one FullEnrich waterfall job for the selected professional fields."""
    field_map = {
        "work_email": "contact.work_emails",
        "phone": "contact.phones",
    }
    row: dict[str, Any] = {
        "first_name": contact.first_name.strip(),
        "last_name": contact.last_name.strip(),
        "enrich_fields": [field_map[field] for field in dict.fromkeys(contact.fields)],
    }
    if contact.company_domain:
        row["domain"] = contact.company_domain
    if contact.company_name:
        row["company_name"] = contact.company_name
    if contact.linkedin_url:
        row["linkedin_url"] = contact.linkedin_url
    response = _request_json(
        FULLENRICH_BASE,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        payload={
            "name": f"Lead Studio - {contact.first_name} {contact.last_name}",
            "data": [row],
        },
        timeout=timeout,
    )
    return EnrichmentJob(
        provider="fullenrich",
        job_id=str(response.get("enrichment_id") or ""),
    )


def poll_contact_lookup(
    provider: Provider,
    job_id: str,
    *,
    field: EnrichmentField | None = None,
    cascade_state: EnrichmentCascadeState | None = None,
    timeout: int = 30,
) -> EnrichmentResult:
    """Poll an already-paid job without submitting a new lookup."""
    if not job_id.strip():
        raise ValueError("L'identifiant de recherche est requis.")
    key = _api_key(provider)
    if provider == "enrow":
        if field not in {"work_email", "phone"}:
            raise ValueError("Le champ Enrow work_email ou phone est requis.")
        path = "email/find/single" if field == "work_email" else "phone/single"
        payload = _request_json(
            f"{ENROW_BASE}/{path}?{urlencode({'id': job_id})}",
            method="GET",
            headers={"x-api-key": key},
            timeout=timeout,
        )
        qualification = str(payload.get("qualification") or "unknown").lower()
        if qualification in {"ongoing", "created", "pending", "processing"}:
            normalized_status: EnrichmentStatus = "pending"
        elif qualification in {"valid", "found"}:
            normalized_status = "finished"
        elif qualification in {"invalid", "not_found", "not found", "no_match"}:
            normalized_status = "not_found"
        elif qualification in {"canceled", "cancelled"}:
            normalized_status = "canceled"
        elif qualification in {"rate_limit", "rate_limited"}:
            normalized_status = "rate_limited"
        elif qualification in {"failed", "error"}:
            normalized_status = "failed"
        else:
            normalized_status = "unknown"
        result = EnrichmentResult(
            provider="enrow",
            job_id=job_id,
            status=normalized_status,
            work_emails=([str(payload["email"])] if payload.get("email") else []),
            phones=([str(payload["number"])] if payload.get("number") else []),
            raw_qualification=qualification,
            credits_used=payload.get("credits_used"),
        )
        if cascade_state is not None:
            expected_job = cascade_state.enrow_job_ids.get(field)
            if expected_job != job_id:
                raise ValueError("Ce job Enrow n'appartient pas à la cascade fournie.")
            cascade_state.enrow_results[field] = result
        return result

    payload = _request_json(
        f"{FULLENRICH_BASE}/{job_id}",
        method="GET",
        headers={"Authorization": f"Bearer {key}"},
        timeout=timeout,
    )
    if cascade_state is not None and cascade_state.fullenrich_job_id != job_id:
        raise ValueError("Ce job FullEnrich n'appartient pas à la cascade fournie.")
    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    first = rows[0] if rows and isinstance(rows[0], dict) else {}
    contact_data = (
        first.get("contact_info")
        if isinstance(first.get("contact_info"), dict)
        else first
    )
    work_email_items = contact_data.get("work_emails", []) if contact_data else []
    phone_items = contact_data.get("phones", []) if contact_data else []
    email_details = []
    for item in work_email_items if isinstance(work_email_items, list) else []:
        if isinstance(item, str) and item.strip():
            email_details.append(EnrichedEmail(email=item.strip(), status="UNKNOWN"))
        elif isinstance(item, dict) and str(item.get("email") or "").strip():
            email_details.append(
                EnrichedEmail(
                    email=str(item["email"]).strip(),
                    status=str(item.get("status") or "UNKNOWN").upper(),
                )
            )
    most_probable_email = (
        contact_data.get("most_probable_work_email")
        if isinstance(contact_data, dict)
        and isinstance(contact_data.get("most_probable_work_email"), dict)
        else None
    )
    if most_probable_email and str(most_probable_email.get("email") or "").strip():
        email = str(most_probable_email["email"]).strip()
        if all(item.email != email for item in email_details):
            email_details.insert(
                0,
                EnrichedEmail(
                    email=email,
                    status=str(most_probable_email.get("status") or "UNKNOWN").upper(),
                ),
            )
    phone_details = []
    for item in phone_items if isinstance(phone_items, list) else []:
        if isinstance(item, str) and item.strip():
            phone_details.append(EnrichedPhone(number=item.strip()))
        elif isinstance(item, dict) and str(item.get("number") or "").strip():
            phone_details.append(
                EnrichedPhone(
                    number=str(item["number"]).strip(),
                    region=item.get("region"),
                    line_type=item.get("line_type"),
                    line_status=item.get("line_status"),
                    ownership_match=item.get("ownership_match"),
                    ownership_match_confidence=item.get("ownership_match_confidence"),
                    connect_rate=item.get("connect_rate"),
                )
            )

    profile = first.get("profile") if isinstance(first.get("profile"), dict) else {}
    employment = (
        profile.get("employment") if isinstance(profile.get("employment"), dict) else {}
    )
    current = (
        employment.get("current")
        if isinstance(employment.get("current"), dict)
        else None
    )
    normalized_employment = None
    if current and current.get("is_current") is not False:
        company = (
            current.get("company") if isinstance(current.get("company"), dict) else {}
        )
        socials = (
            company.get("social_profiles")
            if isinstance(company.get("social_profiles"), dict)
            else {}
        )
        professional_network = (
            socials.get("professional_network")
            if isinstance(socials.get("professional_network"), dict)
            else {}
        )
        normalized_employment = CurrentEmployment(
            title=current.get("title"),
            seniority=current.get("seniority"),
            start_at=current.get("start_at"),
            is_current=True,
            company_name=company.get("name"),
            company_domain=company.get("domain"),
            company_website=company.get("website"),
            company_linkedin_url=professional_network.get("url"),
            company_logo_url=company.get("logo_url"),
        )
    profile_socials = (
        profile.get("social_profiles")
        if isinstance(profile.get("social_profiles"), dict)
        else {}
    )
    profile_network = (
        profile_socials.get("professional_network")
        if isinstance(profile_socials.get("professional_network"), dict)
        else {}
    )

    raw_status = str(payload.get("status") or "UNKNOWN").upper()
    status_map: dict[str, EnrichmentStatus] = {
        "CREATED": "pending",
        "IN_PROGRESS": "pending",
        "FINISHED": "finished",
        "CANCELED": "canceled",
        "CREDITS_INSUFFICIENT": "insufficient_credits",
        "RATE_LIMIT": "rate_limited",
        "UNKNOWN": "unknown",
    }
    normalized_status = status_map.get(raw_status, "unknown")
    usable_emails = [
        item.email
        for item in email_details
        if item.status not in {"INVALID", "INVALID_DOMAIN"}
    ]
    most_probable_phone = (
        contact_data.get("most_probable_phone")
        if isinstance(contact_data, dict)
        and isinstance(contact_data.get("most_probable_phone"), dict)
        else None
    )
    if most_probable_phone and str(most_probable_phone.get("number") or "").strip():
        number = str(most_probable_phone["number"]).strip()
        if all(item.number != number for item in phone_details):
            phone_details.insert(
                0,
                EnrichedPhone(
                    number=number,
                    region=most_probable_phone.get("region"),
                    line_type=most_probable_phone.get("line_type"),
                    line_status=most_probable_phone.get("line_status"),
                    ownership_match=most_probable_phone.get("ownership_match"),
                    ownership_match_confidence=most_probable_phone.get(
                        "ownership_match_confidence"
                    ),
                    connect_rate=most_probable_phone.get("connect_rate"),
                ),
            )
    usable_phones = (
        [str(most_probable_phone["number"]).strip()]
        if most_probable_phone and str(most_probable_phone.get("number") or "").strip()
        else [
            item.number
            for item in phone_details
            if item.line_status != "INACTIVE"
            and item.ownership_match != "MISMATCH"
            and item.line_type in {None, "MOBILE"}
        ]
    )
    if normalized_status == "finished" and not usable_emails and not usable_phones:
        normalized_status = "not_found"
    cost = payload.get("cost") if isinstance(payload.get("cost"), dict) else {}
    return EnrichmentResult(
        provider="fullenrich",
        job_id=job_id,
        status=normalized_status,
        work_emails=list(dict.fromkeys(usable_emails)),
        phones=list(dict.fromkeys(usable_phones)),
        work_email_details=email_details,
        phone_details=phone_details,
        current_employment=normalized_employment,
        professional_profile_url=profile_network.get("url"),
        credits_used=cost.get("credits"),
        raw_qualification=raw_status,
    )
