"""Tests for official-site and strict person-image extraction."""

# SYNTHETIC_TEST_DATA: all identities and URLs below are fictional.

from datetime import date

from leadgenerator.research.visuals import (
    extract_person_profile_images,
    extract_visual_candidates,
)


def test_extract_visuals_prefers_declared_logo_and_social_image():
    """Structured and social metadata retain their official page evidence."""
    html = """
    <html><head>
      <script type="application/ld+json">
        {"@type":"Organization","logo":{"url":"/brand/logo.svg"}}
      </script>
      <meta property="og:image" content="/images/team.jpg">
    </head><body><img class="logo" src="/brand/logo.svg"></body></html>
    """

    candidates = extract_visual_candidates(html, "https://example.com/about")

    assert [(item.kind, item.image_url) for item in candidates] == [
        ("logo", "https://example.com/brand/logo.svg"),
        ("representative_image", "https://example.com/images/team.jpg"),
    ]
    assert all(item.source_url == "https://example.com/about" for item in candidates)


def test_person_image_requires_exact_json_ld_name():
    html = """
    <script type="application/ld+json">
      {"@type":"Person","name":"Alice Martin","image":{"url":"/alice.jpg"}}
    </script>
    """
    candidates = extract_person_profile_images(
        html,
        "https://company.example/team/alice",
        "Alice Martin",
        observed_on=date(2026, 9, 8),
        source_type="official_company",
    )

    assert len(candidates) == 1
    assert candidates[0].image_url == "https://company.example/alice.jpg"
    assert candidates[0].evidence.person_name == "Alice Martin"
    assert candidates[0].evidence.observed_on == date(2026, 9, 8)

    assert (
        extract_person_profile_images(
            html,
            "https://company.example/team/alice",
            "Alice Martine",
            observed_on=date(2026, 9, 8),
        )
        == []
    )


def test_open_graph_person_image_needs_independent_exact_name_marker():
    vague = """
    <head>
      <meta property="og:title" content="Alice Martin, CEO">
      <meta property="og:image" content="/alice.jpg">
    </head>
    """
    exact = """
    <head><meta property="og:image" content="/alice.jpg"></head>
    <body><h1>Alice Martin</h1></body>
    """

    assert (
        extract_person_profile_images(
            vague,
            "https://profiles.example/alice",
            "Alice Martin",
            observed_on=date(2026, 9, 8),
        )
        == []
    )
    assert (
        len(
            extract_person_profile_images(
                exact,
                "https://profiles.example/alice",
                "Alice Martin",
                observed_on=date(2026, 9, 8),
            )
        )
        == 1
    )


def test_linkedin_html_is_never_used_for_profile_image_collection():
    html = """
    <script type="application/ld+json">
      {"@type":"Person","name":"Alice Martin","image":"/alice.jpg"}
    </script>
    """
    assert (
        extract_person_profile_images(
            html,
            "https://www.linkedin.com/in/alice-martin",
            "Alice Martin",
            observed_on=date(2026, 9, 8),
        )
        == []
    )


def test_person_image_rejects_private_or_credentialed_urls():
    private_image = """
    <script type="application/ld+json">
      {"@type":"Person","name":"Alice Martin","image":"http://127.0.0.1/a.jpg"}
    </script>
    """
    userinfo = "user" + ":" + "pass"
    credentialed_image = f"""
    <script type="application/ld+json">
      {{"@type":"Person","name":"Alice Martin","image":"https://{userinfo}@cdn.example/a.jpg"}}
    </script>
    """

    assert (
        extract_person_profile_images(
            private_image,
            "https://profiles.example/alice",
            "Alice Martin",
            observed_on=date(2026, 9, 8),
        )
        == []
    )
    assert (
        extract_person_profile_images(
            credentialed_image,
            "https://profiles.example/alice",
            "Alice Martin",
            observed_on=date(2026, 9, 8),
        )
        == []
    )
