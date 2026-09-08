"""Tests for objective selection and ambiguity handling."""

from pathlib import Path

from leadgenerator.profiles.objectives import (
    OBJECTIVE_SETUP_PROMPT,
    ObjectiveExample,
    ObjectiveStore,
)


def _create_two_objectives(tmp_path: Path) -> ObjectiveStore:
    store = ObjectiveStore(tmp_path / "objectives")
    store.create(
        objective_id="construction",
        name="Construction",
        description="Prospecter les entreprises du BTP et leurs chantiers",
        instructions="Chercher des signaux publics de croissance.",
        triggers=["construction", "entreprise BTP", "nouveau chantier"],
        examples=[
            ObjectiveExample(
                request="Trouve des entreprises du BTP qui recrutent",
                expected_focus="Actualité, recrutements et dirigeant",
            )
        ],
    )
    store.create(
        objective_id="restauration",
        name="Restauration",
        description="Prospecter les groupes de restaurants",
        instructions="Chercher des ouvertures récentes.",
        triggers=["restaurant", "restauration", "nouvelle ouverture"],
        examples=[
            ObjectiveExample(
                request="Trouve des restaurants qui ouvrent une nouvelle adresse",
                expected_focus="Ouverture, fondateur et responsable réseau",
            )
        ],
    )
    return store


def test_explicit_scope_has_priority_and_becomes_sticky(tmp_path: Path):
    store = _create_two_objectives(tmp_path)

    explicit = store.route(
        "Trouve des restaurants",
        conversation_id="thread-123",
        explicit_objective_id="construction",
    )
    following = store.route(
        "Et trouve maintenant leur dirigeant", conversation_id="thread-123"
    )

    assert explicit.status == "selected"
    assert explicit.objective_id == "construction"
    assert explicit.reason == "explicit_objective"
    assert following.objective_id == "construction"
    assert following.reason == "sticky_conversation_objective"


def test_only_objective_is_automatic_for_lead_work(tmp_path: Path):
    store = ObjectiveStore(tmp_path / "objectives")
    store.create(
        objective_id="construction",
        name="Construction",
        description="Entreprises du BTP",
        instructions="Qualifier les prospects.",
    )

    lead_decision = store.route("Trouve-moi des leads dans la construction")
    unrelated_decision = store.route("Quelle heure est-il ?")

    assert lead_decision.objective_id == "construction"
    assert lead_decision.reason == "only_objective_for_lead_work"
    assert unrelated_decision.status == "not_applicable"


def test_industrial_request_is_recognized_without_the_word_lead(tmp_path: Path):
    """The natural starter wording must enter the configured lead workflow."""
    store = ObjectiveStore(tmp_path / "objectives")
    store.create(
        objective_id="industrie",
        name="Industrie",
        description="Prospecter les industriels des Hauts-de-France",
        instructions="Qualifier les entreprises avec des faits publics.",
    )

    decision = store.route("Trouve-moi des industriels dans la métropole lilloise")

    assert decision.status == "selected"
    assert decision.objective_id == "industrie"
    assert decision.reason == "only_objective_for_lead_work"


def test_triggers_and_examples_select_a_clear_objective(tmp_path: Path):
    store = _create_two_objectives(tmp_path)

    decision = store.route("Je cherche une entreprise BTP avec un nouveau chantier")

    assert decision.status == "selected"
    assert decision.objective_id == "construction"
    assert decision.reason == "best_trigger_and_example_match"
    assert decision.candidates[0].score > decision.candidates[1].score


def test_several_plausible_objectives_require_clarification(tmp_path: Path):
    store = _create_two_objectives(tmp_path)

    decision = store.route(
        "Trouve une entreprise BTP de construction avec un nouveau chantier et "
        "un restaurant de restauration avec une nouvelle ouverture"
    )

    assert decision.status == "ambiguous"
    assert decision.objective_id is None
    assert {candidate.objective_id for candidate in decision.candidates} == {
        "construction",
        "restauration",
    }
    assert decision.clarification_prompt == (
        "Dans quel objectif sommes-nous ? Choisissez parmi : "
        "Construction, Restauration."
    )


def test_no_objective_and_no_match_are_explicit_states(tmp_path: Path):
    empty = ObjectiveStore(tmp_path / "empty")
    unconfigured = empty.route("Trouve des leads dans l'industrie")

    assert unconfigured.status == "unconfigured"
    assert unconfigured.clarification_prompt == OBJECTIVE_SETUP_PROMPT
    assert "Exemple" in unconfigured.clarification_prompt
    assert "maintenance prédictive" in unconfigured.clarification_prompt

    configured = _create_two_objectives(tmp_path)
    decision = configured.route("Rédige un haïku sur la pluie")
    assert decision.status == "not_applicable"
    assert decision.objective_id is None


def test_generic_lead_work_requires_an_objective_choice(tmp_path: Path):
    store = _create_two_objectives(tmp_path)

    decision = store.route("Trouve-moi des leads dans l'industrie")

    assert decision.status == "ambiguous"
    assert decision.reason == "lead_work_without_matching_objective"
    assert decision.clarification_prompt == (
        "Quel objectif faut-il utiliser pour cette recherche ? Choisissez parmi : "
        "Construction, Restauration, ou décrivez un nouvel objectif."
    )
