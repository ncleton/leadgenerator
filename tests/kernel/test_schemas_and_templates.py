"""Prevent public schemas, manifests, docs, and synthetic templates from drifting."""

import json
from pathlib import Path

import jsonschema
import yaml
from leadgenerator.kernel.composition import ClientPack
from leadgenerator.kernel.plugins import PluginManifest

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "plugins/leadgenerator/src/leadgenerator/kernel/schemas"
TEMPLATES = ROOT / "plugins/leadgenerator/skills/lead-customization/templates"


def test_every_public_json_schema_is_draft_2020_12_valid():
    paths = sorted(SCHEMAS.glob("*.schema.json"))
    assert len(paths) >= 4
    for path in paths:
        schema = json.loads(path.read_text())
        assert schema["$schema"].endswith("2020-12/schema")
        jsonschema.Draft202012Validator.check_schema(schema)


def test_client_pack_template_matches_runtime_contract():
    values = yaml.safe_load((TEMPLATES / "client-pack.yaml").read_text())
    pack = ClientPack.model_validate(values)
    assert pack.spec.ui.shell_provider == "yaka.ui-workspace"


def test_plugin_templates_have_valid_manifest_shapes(tmp_path):
    for template in (
        "native-plugin.yaml",
        "executable-plugin.yaml",
        "ui-shell-plugin.yaml",
    ):
        values = yaml.safe_load((TEMPLATES / template).read_text())
        root = tmp_path / template
        root.mkdir()
        (root / "config.schema.json").write_text(
            json.dumps({"type": "object", "additionalProperties": False})
        )
        if template == "ui-shell-plugin.yaml":
            (root / "explorer.html").write_text("<html>explorer</html>")
            (root / "workspace.html").write_text("<html>workspace</html>")
        path = root / "plugin.yaml"
        path.write_text(yaml.safe_dump(values, sort_keys=False))
        manifest = PluginManifest.load(path)
        assert manifest.api_version == "leadgenerator.yaka/v1"
