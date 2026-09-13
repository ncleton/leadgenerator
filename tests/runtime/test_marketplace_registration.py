"""Installing a copied folder rebinds only the product's own marketplace."""

import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module():
    spec = importlib.util.spec_from_file_location(
        "marketplace_registration", ROOT / "scripts/register_codex_marketplace.py"
    )
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.mark.parametrize("previous", [None, "same", "other"])
def test_register_selects_only_the_requested_source(tmp_path, previous):
    selected = tmp_path / "new/code"
    commands = []
    records = [{"name": "unrelated", "root": str(tmp_path / "unrelated")}]
    if previous:
        records.append(
            {
                "name": "leadgenerator-local",
                "root": str(selected if previous == "same" else tmp_path / "old/code"),
            }
        )

    def run(args, **kwargs):
        commands.append(args[3:])
        return SimpleNamespace(stdout=json.dumps({"marketplaces": records}))

    module().register(selected, "codex", run=run)
    assert commands[0] == ["list", "--json"]
    if previous == "same":
        assert len(commands) == 1
    else:
        assert commands[-1] == ["add", str(selected)]
        assert (["remove", "leadgenerator-local"] in commands) == (previous == "other")


def test_failed_rebind_restores_previous_marketplace(tmp_path):
    commands = []
    previous = str(tmp_path / "old/code")
    selected = tmp_path / "new/code"

    def run(args, **kwargs):
        commands.append(args[3:])
        if args[3:] == ["add", str(selected)]:
            raise subprocess.CalledProcessError(1, args)
        return SimpleNamespace(
            stdout=json.dumps(
                {
                    "marketplaces": [
                        {
                            "name": "leadgenerator-local",
                            "root": previous,
                        }
                    ]
                }
            )
        )

    with pytest.raises(RuntimeError, match="Cannot register"):
        module().register(selected, "codex", run=run)
    assert commands[-1] == ["add", previous]
