"""Tests for the explicit public-only LinkedIn capability boundary."""

from leadgenerator.research.linkedin_public import linkedin_public_capabilities


def test_linkedin_capabilities_never_claim_a_personal_session():
    capabilities = linkedin_public_capabilities()

    assert capabilities["mode"] == "public_only"
    assert capabilities["status"] == "available"
    assert capabilities["personal_account"]["connected"] is None
    assert (
        capabilities["personal_account"]["verification"]
        == "not_checked_by_public_provider"
    )
    assert capabilities["personal_account"]["credentials_accepted"] is False
    assert capabilities["authenticated_browser_provider"] == "linkedin.session"
    assert "cookie_import_or_export" in capabilities["unsupported"]
    assert "objective_specific_top_five_ranking" in capabilities["supported"]
