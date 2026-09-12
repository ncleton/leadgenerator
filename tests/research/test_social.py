"""Tests for the read-only Agent Reach-derived social connectors."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from leadgenerator.research import social
from pydantic import ValidationError


def request(**updates) -> social.SocialQuery:
    values = {
        "objective_id": "objectif-test",
        "platform": "instagram",
        "operation": "profile",
        "target": "example-company",
        "allow_authenticated_session": True,
    }
    values.update(updates)
    return social.SocialQuery(**values)


def test_authenticated_social_read_requires_explicit_consent():
    with pytest.raises(ValidationError, match="explicitement autorisée"):
        request(allow_authenticated_session=False)


@pytest.mark.parametrize(
    ("platform", "operation"),
    [
        ("x", "post"),
        ("reddit", "comment"),
        ("facebook", "notifications"),
        ("instagram", "follow"),
    ],
)
def test_opencli_write_or_private_operations_are_not_exposed(platform, operation):
    with pytest.raises(ValueError, match="non autorisée"):
        social._run_opencli(
            request(platform=platform, operation=operation),
            timeout=30,
        )


def test_opencli_runs_a_real_allow_listed_command_and_keeps_provenance(monkeypatch):
    monkeypatch.setattr(
        social,
        "check_social_connectors",
        lambda: {"connectors": {"opencli": {"state": "ready"}}},
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        payload = {
            "username": "example-company",
            "url": "https://www.instagram.com/example-company/",
        }
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload).encode(),
            stderr=b"",
        )

    monkeypatch.setattr(social.subprocess, "run", fake_run)

    result = social.run_social_query(request(), timeout=30)

    assert calls[0][0] == [
        "opencli",
        "instagram",
        "profile",
        "example-company",
        "-f",
        "json",
    ]
    assert result["objective_id"] == "objectif-test"
    assert result["backend"] == "opencli"
    assert result["source_urls"] == ["https://www.instagram.com/example-company/"]
    assert result["trust"] == "untrusted_authenticated_social_content"


def test_opencli_fails_loudly_when_browser_bridge_is_not_ready(monkeypatch):
    monkeypatch.setattr(
        social,
        "check_social_connectors",
        lambda: {
            "connectors": {
                "opencli": {
                    "state": "setup_required",
                    "action": "Activer l'extension OpenCLI.",
                }
            }
        },
    )

    with pytest.raises(RuntimeError, match="Activer l'extension"):
        social.run_social_query(request(), timeout=30)


def test_linkedin_only_calls_read_tools_and_preserves_source_urls(monkeypatch):
    monkeypatch.setattr(
        social,
        "check_social_connectors",
        lambda: {"connectors": {"linkedin": {"state": "configured"}}},
    )
    call = AsyncMock(
        return_value={
            "url": "https://www.linkedin.com/company/example/",
            "sections": {"posts": "Publication récente"},
        }
    )
    monkeypatch.setattr(social, "_call_linkedin_tool", call)

    result = social.run_social_query(
        request(
            platform="linkedin",
            operation="get_company_profile",
            target="example",
            sections="posts",
        ),
        timeout=30,
    )

    call.assert_awaited_once_with(
        "get_company_profile",
        {"company_name": "example", "sections": "posts"},
        timeout=30,
    )
    assert result["backend"] == social.LINKEDIN_MCP_PACKAGE
    assert result["source_urls"] == ["https://www.linkedin.com/company/example/"]


def test_linkedin_messaging_and_connection_tools_are_not_exposed():
    for operation in ("send_message", "connect_with_person", "get_inbox"):
        with pytest.raises(ValueError, match="non autorisée"):
            social._linkedin_arguments(
                request(
                    platform="linkedin",
                    operation=operation,
                    target="example",
                )
            )
