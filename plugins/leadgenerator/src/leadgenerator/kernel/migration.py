"""Idempotent migration entry point for modular private runtime state."""

from __future__ import annotations

import json

from leadgenerator.kernel.composition import LeadGeneratorRuntime
from leadgenerator.persistence.company_memory import CompanyMemory


def migrate_modular_runtime() -> dict[str, object]:
    """Create canonical stores, health-check plugins, then record their versions."""
    runtime = LeadGeneratorRuntime()
    memory = CompanyMemory()
    try:
        status = memory.status()
        recorded = []
        for row in runtime.report()["plugins"]:
            if row["state"] != "active":
                continue
            memory.record_plugin_state(
                row["id"], row["version"], row["state"], migration_version="1.0"
            )
            recorded.append(row["id"])
        return {
            "status": "ok",
            "schema": "leadgenerator_private",
            "migration_version": "1.0",
            "plugins_recorded": recorded,
            "stored_companies": status["stored_companies"],
            "stored_snapshots": status["stored_snapshots"],
        }
    finally:
        runtime.manager.stop_all()


def main() -> None:
    """Print only non-secret migration metadata for local installers."""
    print(json.dumps(migrate_modular_runtime(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
