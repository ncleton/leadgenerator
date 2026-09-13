"""Persistent schedule lifecycle and objective isolation, without live jobs."""

import json
import shutil

import pytest
from leadgenerator.profiles import schedules as schedules_module
from leadgenerator.profiles.objectives import ObjectiveStore
from leadgenerator.profiles.schedules import ObjectiveScheduleStore, ScheduleSettings
from pydantic import ValidationError


@pytest.fixture
def schedules(tmp_path):
    objectives = ObjectiveStore(tmp_path / "objectives")
    for identifier in ("alpha", "beta"):
        objectives.create(
            objective_id=identifier,
            name=identifier.title(),
            description="Synthetic offer",
            instructions="Use public evidence.",
        )
    return ObjectiveScheduleStore(objectives)


def _run_context(store, objective_id):
    """Simulate the installation binding supplied by a newly configured prompt."""
    return store.run_context(
        objective_id,
        expected_installation_binding=store.handoff(objective_id)[
            "installation_binding"
        ],
    )


def test_defaults_are_local_nine_am_and_disabled(schedules):
    schedule = schedules.load("alpha")
    assert schedule.settings.local_time == "09:00"
    assert schedule.settings.timezone == "Europe/Paris"
    assert schedule.settings.lead_count == 10
    assert schedule.sync_status == "not_configured"
    assert not _run_context(schedules, "alpha")["run_authorized"]


def test_claude_can_read_but_cannot_mutate_a_codex_schedule(schedules, monkeypatch):
    schedules.save("alpha", ScheduleSettings(enabled=True))
    schedules.confirm("alpha", revision=1, automation_id="job-alpha", status="ACTIVE")
    original = schedules.load("alpha").model_dump()
    monkeypatch.setenv("LEADGENERATOR_HOST", "claude")
    handoff = schedules.handoff("alpha")
    assert handoff["next_action"] == "manage_in_codex"
    assert handoff["schedule"]["host_editable"] is False
    assert handoff["schedule"]["sync_status"] == "active"
    with pytest.raises(ValueError, match="Codex"):
        schedules.save("alpha", ScheduleSettings(enabled=False))
    with pytest.raises(ValueError, match="Codex"):
        schedules.confirm(
            "alpha", revision=1, automation_id="job-alpha", status="ACTIVE"
        )
    assert schedules.load("alpha").model_dump() == original


def test_save_confirm_reload_edit_and_pause_are_distinct(schedules):
    saved = schedules.save("alpha", ScheduleSettings(enabled=True))
    assert saved.sync_status == "pending"
    assert not _run_context(schedules, "alpha")["run_authorized"]
    schedules.confirm(
        "alpha", revision=saved.revision, automation_id="job-alpha", status="ACTIVE"
    )
    reloaded = ObjectiveScheduleStore(schedules.objectives)
    assert _run_context(reloaded, "alpha")["run_authorized"]
    assert reloaded.load("beta").sync_status == "not_configured"
    changed = reloaded.save(
        "alpha", ScheduleSettings(enabled=True, lead_count=17, local_time="10:30")
    )
    assert changed.automation_id == "job-alpha"
    assert changed.sync_status == "pending"
    assert not _run_context(reloaded, "alpha")["run_authorized"]
    with pytest.raises(ValueError, match="changed"):
        reloaded.confirm(
            "alpha", revision=saved.revision, automation_id="job-alpha", status="ACTIVE"
        )
    reloaded.confirm(
        "alpha", revision=changed.revision, automation_id="job-alpha", status="ACTIVE"
    )
    assert _run_context(reloaded, "alpha")["lead_count"] == 17
    paused = reloaded.save(
        "alpha", changed.settings.model_copy(update={"enabled": False})
    )
    assert not _run_context(reloaded, "alpha")["run_authorized"]
    reloaded.confirm(
        "alpha", revision=paused.revision, automation_id="job-alpha", status="PAUSED"
    )
    assert reloaded.load("alpha").sync_status == "paused"


def test_repeated_save_is_idempotent_and_different_stale_save_rejected(schedules):
    saved = schedules.save("alpha", ScheduleSettings(enabled=True))
    assert schedules.save("alpha", saved.settings).revision == saved.revision
    with pytest.raises(ValueError, match="changé"):
        schedules.save(
            "alpha", ScheduleSettings(enabled=True, lead_count=2), expected_revision=0
        )


def test_automation_cannot_be_duplicated_or_reused_for_another_objective(schedules):
    for identifier in ("alpha", "beta"):
        schedules.save(identifier, ScheduleSettings(enabled=True))
    schedules.confirm("alpha", revision=1, automation_id="job-a", status="ACTIVE")
    with pytest.raises(ValueError, match="another objective"):
        schedules.confirm("beta", revision=1, automation_id="job-a", status="ACTIVE")
    with pytest.raises(ValueError, match="duplicate"):
        schedules.confirm("alpha", revision=1, automation_id="job-b", status="ACTIVE")
    with pytest.raises(ValueError, match="status"):
        schedules.confirm("alpha", revision=1, automation_id="job-a", status="PAUSED")


def test_archived_objectives_stop_runs_and_cannot_be_enabled(schedules):
    schedules.save("alpha", ScheduleSettings(enabled=True))
    schedules.confirm("alpha", revision=1, automation_id="job-a", status="ACTIVE")
    schedules.objectives.archive("alpha")
    assert not _run_context(schedules, "alpha")["run_authorized"]
    with pytest.raises(ValueError, match="archived"):
        schedules.save("alpha", ScheduleSettings(enabled=True))


@pytest.mark.parametrize(
    "values",
    [
        {"local_time": "24:00"},
        {"local_time": "9:00"},
        {"timezone": "Unknown/Nowhere"},
        {"lead_count": 26},
        {"lead_count": 0},
        {"weekdays": []},
        {"weekdays": [8]},
    ],
)
def test_invalid_schedule_values_are_rejected(values):
    with pytest.raises(ValidationError):
        ScheduleSettings(**values)


def test_handoff_preserves_wall_clock_and_loads_fresh_context(schedules):
    schedules.save(
        "alpha", ScheduleSettings(enabled=True, frequency="weekly", weekdays=[5, 1, 5])
    )
    handoff = schedules.handoff("alpha")
    assert handoff["when"] == "Chaque lundi, vendredi à 09:00 (Europe/Paris)"
    assert handoff["next_action"] == "configure_host_automation"
    assert handoff["automation_marker"] == (
        f"[leadgenerator-installation:{handoff['installation_binding']}]"
        "[leadgenerator-objective:alpha]"
    )
    assert "get_lead_objective_schedule_run" in handoff["prompt"]
    assert (
        f"expected_installation_binding={handoff['installation_binding']}"
        in handoff["prompt"]
    )
    schedules.objectives.recompile_agent("alpha", instructions="New evidence rules.")
    assert "New evidence rules" not in schedules.handoff("alpha")["prompt"]
    assert "actuels" in handoff["prompt"]


def test_missing_and_conflicting_objective_ids_are_rejected(schedules):
    with pytest.raises((KeyError, ValueError)):
        schedules.load("missing")
    with pytest.raises(ValueError):
        schedules.load("../alpha")


def test_copied_schedule_requires_reconfiguration_without_changing_desired_settings(
    schedules, tmp_path
):
    desired = ScheduleSettings(enabled=True, frequency="weekly", lead_count=19)
    saved = schedules.save("alpha", desired)
    confirmed = schedules.confirm(
        "alpha", revision=saved.revision, automation_id="original-job", status="ACTIVE"
    )
    copied_home = tmp_path / "copied" / "objectives"
    shutil.copytree(schedules.objectives.home, copied_home)
    copied = ObjectiveScheduleStore(ObjectiveStore(copied_home))
    path = copied_home / "alpha" / "schedule.json"
    unchanged_bytes = path.read_bytes()

    loaded = copied.load("alpha")

    assert loaded.settings == desired
    assert loaded.revision == confirmed.revision
    assert loaded.automation_id is None
    assert loaded.confirmed_status is None
    assert loaded.synced_revision is None
    assert loaded.sync_status == "needs_reconfiguration"
    assert _run_context(copied, "alpha")["run_authorized"] is False
    assert (
        _run_context(copied, "alpha")["reason"]
        == "schedule_requires_local_reconfiguration"
    )
    handoff = copied.handoff("alpha")
    assert handoff["next_action"] == "configure_host_automation"
    assert handoff["schedule"]["requires_reconfiguration"] is True
    assert (
        handoff["automation_marker"] != schedules.handoff("alpha")["automation_marker"]
    )
    assert "original-job" not in json.dumps(handoff)
    assert path.read_bytes() == unchanged_bytes
    assert _run_context(schedules, "alpha")["run_authorized"] is True

    copied.confirm(
        "alpha", revision=loaded.revision, automation_id="copied-job", status="ACTIVE"
    )
    assert _run_context(copied, "alpha")["run_authorized"] is True
    assert copied.load("alpha").settings == desired
    assert schedules.load("alpha").automation_id == "original-job"


def test_same_path_on_a_different_computer_requires_reconfiguration(
    schedules, monkeypatch
):
    monkeypatch.setattr(
        schedules_module.socket, "gethostname", lambda: "example-host-a"
    )
    schedules.save("alpha", ScheduleSettings(enabled=True))
    schedules.confirm("alpha", revision=1, automation_id="job-alpha", status="ACTIVE")
    assert _run_context(schedules, "alpha")["run_authorized"] is True

    monkeypatch.setattr(
        schedules_module.socket, "gethostname", lambda: "example-host-b"
    )

    assert schedules.load("alpha").sync_status == "needs_reconfiguration"
    assert schedules.load("alpha").automation_id is None
    assert _run_context(schedules, "alpha")["run_authorized"] is False


@pytest.mark.parametrize("enabled,status", [(True, "ACTIVE"), (False, "PAUSED")])
def test_unbound_legacy_confirmation_never_claims_local_scheduler_state(
    schedules, enabled, status
):
    saved = schedules.save("alpha", ScheduleSettings(enabled=enabled))
    schedules.confirm(
        "alpha", revision=saved.revision, automation_id="legacy-job", status=status
    )
    path = schedules.objectives.home / "alpha" / "schedule.json"
    legacy = json.loads(path.read_text(encoding="utf-8"))
    legacy.pop("confirmation_binding")
    path.write_text(json.dumps(legacy), encoding="utf-8")
    original = path.read_bytes()

    loaded = schedules.load("alpha")

    assert loaded.sync_status == "needs_reconfiguration"
    assert loaded.settings.enabled is enabled
    assert loaded.automation_id is None
    assert _run_context(schedules, "alpha")["run_authorized"] is False
    assert path.read_bytes() == original


def test_active_schedule_rejects_missing_or_unrelated_execution_binding(schedules):
    saved = schedules.save("alpha", ScheduleSettings(enabled=True))
    schedules.confirm(
        "alpha", revision=saved.revision, automation_id="job-alpha", status="ACTIVE"
    )

    for binding in (None, "unrelated-installation"):
        result = schedules.run_context("alpha", expected_installation_binding=binding)
        assert result["run_authorized"] is False
        assert result["reason"] == "schedule_installation_binding_missing_or_mismatched"

    assert _run_context(schedules, "alpha")["run_authorized"] is True


def test_original_scheduler_cannot_run_a_reconfirmed_copy(schedules, tmp_path):
    saved = schedules.save("alpha", ScheduleSettings(enabled=True))
    schedules.confirm(
        "alpha", revision=saved.revision, automation_id="original-job", status="ACTIVE"
    )
    original_binding = schedules.handoff("alpha")["installation_binding"]
    copied_home = tmp_path / "another-installation" / "objectives"
    shutil.copytree(schedules.objectives.home, copied_home)
    copied = ObjectiveScheduleStore(ObjectiveStore(copied_home))
    copied.confirm(
        "alpha", revision=saved.revision, automation_id="copied-job", status="ACTIVE"
    )

    result = copied.run_context("alpha", expected_installation_binding=original_binding)

    assert result["run_authorized"] is False
    assert result["reason"] == "schedule_installation_binding_missing_or_mismatched"
    assert _run_context(copied, "alpha")["run_authorized"] is True
