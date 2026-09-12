"""Persistent schedule lifecycle and objective isolation, without live jobs."""

import pytest
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


def test_defaults_are_local_nine_am_and_disabled(schedules):
    schedule = schedules.load("alpha")
    assert schedule.settings.local_time == "09:00"
    assert schedule.settings.timezone == "Europe/Paris"
    assert schedule.settings.lead_count == 10
    assert schedule.sync_status == "not_configured"
    assert not schedules.run_context("alpha")["run_authorized"]


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
    assert not schedules.run_context("alpha")["run_authorized"]
    schedules.confirm(
        "alpha", revision=saved.revision, automation_id="job-alpha", status="ACTIVE"
    )
    reloaded = ObjectiveScheduleStore(schedules.objectives)
    assert reloaded.run_context("alpha")["run_authorized"]
    assert reloaded.load("beta").sync_status == "not_configured"
    changed = reloaded.save(
        "alpha", ScheduleSettings(enabled=True, lead_count=17, local_time="10:30")
    )
    assert changed.automation_id == "job-alpha"
    assert changed.sync_status == "pending"
    assert not reloaded.run_context("alpha")["run_authorized"]
    with pytest.raises(ValueError, match="changed"):
        reloaded.confirm(
            "alpha", revision=saved.revision, automation_id="job-alpha", status="ACTIVE"
        )
    reloaded.confirm(
        "alpha", revision=changed.revision, automation_id="job-alpha", status="ACTIVE"
    )
    assert reloaded.run_context("alpha")["lead_count"] == 17
    paused = reloaded.save(
        "alpha", changed.settings.model_copy(update={"enabled": False})
    )
    assert not reloaded.run_context("alpha")["run_authorized"]
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
    assert not schedules.run_context("alpha")["run_authorized"]
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
    assert handoff["automation_marker"] == "[leadgenerator-objective:alpha]"
    assert "get_lead_objective_schedule_run" in handoff["prompt"]
    schedules.objectives.recompile_agent("alpha", instructions="New evidence rules.")
    assert "New evidence rules" not in schedules.handoff("alpha")["prompt"]
    assert "actuels" in handoff["prompt"]


def test_missing_and_conflicting_objective_ids_are_rejected(schedules):
    with pytest.raises((KeyError, ValueError)):
        schedules.load("missing")
    with pytest.raises(ValueError):
        schedules.load("../alpha")
