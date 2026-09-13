"""Isolate every test process from installed objectives and business memory."""

from __future__ import annotations

import os
import tempfile

# Configure this before test modules import the MCP singleton. A fixture alone
# runs too late and could initialize a real workspace during collection.
_private_test_home = tempfile.TemporaryDirectory(prefix="leadgenerator-tests-")
os.environ["LEADGENERATOR_HOME"] = _private_test_home.name
os.environ.pop("LEADGENERATOR_DATABASE_URL", None)


def pytest_sessionfinish(session, exitstatus):
    _private_test_home.cleanup()
