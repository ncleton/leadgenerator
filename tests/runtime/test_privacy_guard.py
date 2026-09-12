"""Privacy guard regressions for generated dependency lockfiles."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVACY_GUARD_PATH = ROOT / "scripts" / "agent-privacy-check.py"
SCAN_POLICY = {"max_text_bytes": 2_000_000}


def load_privacy_guard():
    """Load the standalone guard without turning scripts into a package."""
    spec = importlib.util.spec_from_file_location(
        "leadgenerator_privacy_guard", PRIVACY_GUARD_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generated_lockfile_ignores_only_numeric_false_positives():
    """Package hashes must not look like personal phone or banking data."""
    guard = load_privacy_guard()
    phone_like_hash = b"0517" + b"119408"
    iban_like_hash = b"FR76" + (b"0" * 23)
    content = (
        b'source = "https://files.pythonhosted.org/'
        + phone_like_hash
        + b'/package.whl"\nhash = "'
        + iban_like_hash
        + b'"\n'
    )

    assert guard.scan_bytes(content, "plugins/leadgenerator/uv.lock", SCAN_POLICY) == []


def test_generated_lockfile_still_blocks_credentials():
    """The narrow lockfile exemption must never disable credential detection."""
    guard = load_privacy_guard()
    content = b"access_" + b'token = "' + b"realistic_" + b'secret_value_123456"\n'

    assert guard.scan_bytes(content, "plugins/leadgenerator/uv.lock", SCAN_POLICY) == [
        "credential-assignment"
    ]
