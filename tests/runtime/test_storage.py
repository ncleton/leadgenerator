"""Portable project data must never reuse a previous installation implicitly."""

from pathlib import Path

import pytest
from leadgenerator import storage
from leadgenerator.kernel import composition
from leadgenerator.profiles.migration import main as migrate_profiles
from leadgenerator.profiles.objectives import ObjectiveStore
from leadgenerator.profiles.offers import build_profile, load_profiles, save_profile
from leadgenerator.profiles.preferences import load_preferences, set_desired_lead_count
from leadgenerator.profiles.user import (
    build_user_profile,
    load_user_profile,
    save_user_profile,
)
from leadgenerator.storage import (
    StorageConfigurationError,
    private_home,
    private_home_for_code_root,
    private_path,
)


def _source_folder(root: Path, *, git: bool = True) -> Path:
    """Create only public layout markers, not a real checkout or private fixture."""
    for relative in (
        "plugins/leadgenerator/.codex-plugin/plugin.json",
        "plugins/leadgenerator/pyproject.toml",
        "scripts/install_client.sh",
        "plugins/leadgenerator/src/leadgenerator/storage.py",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    if git:
        (root / ".git").mkdir()
    return root / "plugins/leadgenerator/src/leadgenerator/storage.py"


def _save_synthetic_context() -> None:
    ObjectiveStore().create(
        name="Synthetic objective",
        description="Synthetic test context",
        instructions="Use public evidence.",
        triggers=["synthetic"],
    )
    save_user_profile(build_user_profile(seller_website_url="https://example.com"))
    save_profile(
        build_profile(
            seller_name="Example Person",
            seller_company="Example Company",
            offer_name="Synthetic offer",
            offer_description="A synthetic testing offer",
            target_companies="Example companies",
            geography="Example region",
        )
    )
    set_desired_lead_count(23)


def test_source_layout_derives_sibling_data_without_creating_it(tmp_path, monkeypatch):
    code = tmp_path / "workspace" / "code"
    monkeypatch.setattr(storage, "__file__", str(_source_folder(code)))
    monkeypatch.delenv("LEADGENERATOR_HOME", raising=False)

    assert private_home() == code.parent / "donnees-privees"
    assert not private_home().exists()
    assert private_home_for_code_root(code) == private_home()


def test_source_zip_without_git_uses_the_same_portable_layout(tmp_path, monkeypatch):
    code = tmp_path / "bundle" / "code"
    monkeypatch.setattr(storage, "__file__", str(_source_folder(code, git=False)))
    monkeypatch.delenv("LEADGENERATOR_HOME", raising=False)

    assert private_home() == code.parent / "donnees-privees"
    monkeypatch.setenv("LEADGENERATOR_HOME", str(code / "private"))
    with pytest.raises(StorageConfigurationError, match="outside the code"):
        private_home()


def test_neighbor_checkouts_have_distinct_data_roots(tmp_path):
    first = tmp_path / "first-checkout"
    second = tmp_path / "second-checkout"
    _source_folder(first)
    _source_folder(second)

    assert (
        private_home_for_code_root(first) == tmp_path / "first-checkout-donnees-privees"
    )
    assert (
        private_home_for_code_root(second)
        == tmp_path / "second-checkout-donnees-privees"
    )


def test_data_root_requires_a_real_source_layout(tmp_path):
    with pytest.raises(StorageConfigurationError, match="valid Lead Generator source"):
        private_home_for_code_root(tmp_path / "not-a-checkout")


def test_each_bound_project_has_independent_objectives_profiles_and_preferences(
    tmp_path, monkeypatch
):
    first = tmp_path / "one" / "donnees-privees"
    second = tmp_path / "two" / "donnees-privees"
    monkeypatch.setenv("LEADGENERATOR_HOME", str(first))
    _save_synthetic_context()

    monkeypatch.setenv("LEADGENERATOR_HOME", str(second))
    assert private_home() == second
    assert ObjectiveStore().list() == []
    assert load_user_profile() is None
    assert load_profiles() == []
    assert load_preferences().desired_lead_count == 10
    assert not second.exists()

    monkeypatch.setenv("LEADGENERATOR_HOME", str(first))
    assert len(ObjectiveStore().list()) == 1
    assert load_user_profile() is not None
    assert len(load_profiles()) == 1
    assert load_preferences().desired_lead_count == 23


def test_copied_source_without_data_starts_empty_and_never_reads_global_home(
    tmp_path, monkeypatch
):
    old_global = tmp_path / "user" / ".codex" / "leadgenerator"
    monkeypatch.setenv("LEADGENERATOR_HOME", str(old_global))
    _save_synthetic_context()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "user"))
    monkeypatch.delenv("LEADGENERATOR_HOME")
    first_code = tmp_path / "first" / "code"
    second_code = tmp_path / "copy" / "code"
    monkeypatch.setattr(storage, "__file__", str(_source_folder(first_code)))
    _save_synthetic_context()

    monkeypatch.setattr(storage, "__file__", str(_source_folder(second_code)))
    assert private_home() == second_code.parent / "donnees-privees"
    assert ObjectiveStore().list() == []
    assert load_user_profile() is None
    assert load_profiles() == []
    assert load_preferences().desired_lead_count == 10
    assert len(ObjectiveStore(old_global / "objectives").list()) == 1


def test_cached_plugin_requires_binding_and_ignores_global_home_and_cwd(
    tmp_path, monkeypatch
):
    source = tmp_path / ".codex/plugins/cache/example/1.0/src/leadgenerator/storage.py"
    monkeypatch.setattr(storage, "__file__", str(source))
    monkeypatch.delenv("LEADGENERATOR_HOME", raising=False)
    code = tmp_path / "workspace" / "code"
    _source_folder(code)
    monkeypatch.chdir(code)

    with pytest.raises(StorageConfigurationError, match="no private data binding"):
        private_home()
    with pytest.raises(StorageConfigurationError, match="no private data binding"):
        ObjectiveStore()

    private = tmp_path / "workspace" / "donnees-privees"
    monkeypatch.setenv("LEADGENERATOR_HOME", str(private))
    assert private_home() == private
    assert ObjectiveStore().list() == []


@pytest.mark.parametrize("value", ["", "relative/path", "~/private-data"])
def test_invalid_explicit_binding_fails_instead_of_falling_back(value, monkeypatch):
    monkeypatch.setenv("LEADGENERATOR_HOME", value)
    with pytest.raises(StorageConfigurationError):
        private_home()


@pytest.mark.parametrize("git_marker", ["directory", "file"])
def test_private_data_cannot_live_anywhere_inside_a_git_repository(
    tmp_path, monkeypatch, git_marker
):
    repo = tmp_path / "repo"
    repo.mkdir()
    if git_marker == "directory":
        (repo / ".git").mkdir()
    else:
        (repo / ".git").write_text("gitdir: another/location", encoding="utf-8")
    monkeypatch.setenv("LEADGENERATOR_HOME", str(repo / "ignored" / "private"))
    with pytest.raises(StorageConfigurationError, match="outside the code"):
        private_home()


def test_private_data_cannot_live_inside_plugin_cache(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "LEADGENERATOR_HOME", str(tmp_path / ".codex/plugins/cache/plugin/private")
    )
    with pytest.raises(StorageConfigurationError, match="plugin cache"):
        private_home()


def test_storage_symlinks_cannot_redirect_the_private_root_or_its_children(
    tmp_path, monkeypatch
):
    home = tmp_path / "donnees-privees"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    try:
        home.symlink_to(elsewhere, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links are unavailable for this Windows account.")
    monkeypatch.setenv("LEADGENERATOR_HOME", str(home))
    with pytest.raises(StorageConfigurationError, match="symlink"):
        private_home()
    home.unlink()
    home.mkdir()
    (home / "objectives").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(StorageConfigurationError, match="escape"):
        ObjectiveStore()


def test_private_child_path_cannot_traverse_outside_its_root(tmp_path, monkeypatch):
    monkeypatch.setenv("LEADGENERATOR_HOME", str(tmp_path / "donnees-privees"))
    with pytest.raises(StorageConfigurationError, match="escape"):
        private_path("..", "outside")


def test_source_directory_symlink_cannot_redirect_the_derived_data_root(tmp_path):
    code = tmp_path / "original" / "code"
    _source_folder(code)
    link = tmp_path / "linked-code"
    try:
        link.symlink_to(code, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links are unavailable for this Windows account.")
    with pytest.raises(StorageConfigurationError, match="symlink"):
        private_home_for_code_root(link)


def test_runtime_cache_keeps_other_project_owners_alive_when_the_binding_changes(
    tmp_path, monkeypatch
):
    stopped = []

    class FakeRuntime:
        def __init__(self, home):
            self.home = home
            self.manager = self

        def stop_all(self):
            stopped.append(self)

    monkeypatch.setattr(composition, "LeadGeneratorRuntime", FakeRuntime)
    # Collection may already have created the MCP server's startup runtime. This
    # test owns only its temporary cache and must never stop that shared owner.
    monkeypatch.setattr(composition, "_runtimes", {})
    try:
        monkeypatch.setenv("LEADGENERATOR_HOME", str(tmp_path / "first"))
        first = composition.get_runtime()
        assert composition.get_runtime() is first
        monkeypatch.setenv("LEADGENERATOR_HOME", str(tmp_path / "second"))
        second = composition.get_runtime()
        assert second is not first
        assert second.home == tmp_path / "second"
        assert stopped == []

        monkeypatch.setenv("LEADGENERATOR_HOME", str(tmp_path / "first"))
        assert composition.get_runtime() is first
        refreshed = composition.get_runtime(refresh=True)
        assert refreshed is not first
        assert stopped == [first]
        assert composition.get_runtime(home=tmp_path / "second") is second
        assert (
            composition.get_runtime(home=tmp_path / "first" / "child" / "..")
            is refreshed
        )

        composition.reset_runtime()
        assert set(stopped) == {first, second, refreshed}
        assert len(stopped) == 3
        assert composition._runtimes == {}
    finally:
        composition.reset_runtime()


def test_legacy_profile_cli_requires_both_explicit_source_and_confirmation(
    tmp_path, monkeypatch
):
    target = tmp_path / "donnees-privees"
    monkeypatch.setenv("LEADGENERATOR_HOME", str(target))
    with pytest.raises(SystemExit) as missing_source:
        migrate_profiles([])
    assert missing_source.value.code == 2
    with pytest.raises(SystemExit) as missing_confirmation:
        migrate_profiles(["--source-home", str(tmp_path)])
    assert missing_confirmation.value.code == 2
    assert not target.exists()


def test_confirmed_legacy_cli_imports_only_selected_offers_and_preserves_source(
    tmp_path, monkeypatch
):
    old = tmp_path / "old"
    target = tmp_path / "new"
    monkeypatch.setenv("LEADGENERATOR_HOME", str(old))
    _save_synthetic_context()
    old_profile = old / "offer-profiles" / "synthetic-offer.json"
    original = old_profile.read_bytes()
    monkeypatch.setenv("LEADGENERATOR_HOME", str(target))

    migrate_profiles(["--source-home", str(old), "--confirm"])

    assert [item.objective_id for item in ObjectiveStore().list()] == [
        "synthetic-offer"
    ]
    assert load_user_profile() is None
    assert load_preferences().desired_lead_count == 10
    assert old_profile.read_bytes() == original
