"""Tests for shareable per-user integration onboarding."""

from lead_studio.integrations.status import check_integrations


def test_missing_integrations_explain_local_configuration(monkeypatch):
    """Startup diagnostics report purpose without exposing or requiring secrets."""
    for name in ("ENROW_API_KEY", "FULLENRICH_API_KEY", "HUBSPOT_ACCESS_TOKEN"):
        monkeypatch.delenv(name, raising=False)

    statuses = check_integrations(verify=False)

    assert [item.status for item in statuses] == [
        "not_configured",
        "not_configured",
        "not_configured",
    ]
    assert statuses[0].required_env_var == "ENROW_API_KEY"
    assert "Recommandé" in statuses[1].recommendation
    assert "attribuer" in statuses[2].purpose


def test_network_failure_keeps_a_present_key_configured(monkeypatch):
    """A transient network issue is not misreported as an invalid credential."""
    monkeypatch.setenv("ENROW_API_KEY", "present")
    monkeypatch.delenv("FULLENRICH_API_KEY", raising=False)
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(
        "lead_studio.integrations.status._verify",
        lambda _service, _token, _timeout: ("configured", "Réseau indisponible."),
    )

    statuses = check_integrations(verify=True)

    assert statuses[0].status == "configured"
