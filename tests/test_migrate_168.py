"""The production migrations of issue #168 (adhoc/migrate_168_*.py), on plain documents."""
import datetime
import importlib.util
import pathlib

import untitledapp.galaxypolicies as gp
import untitledapp.shared as uas

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOW = datetime.datetime(2026, 11, 23, tzinfo=datetime.timezone.utc)


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "adhoc" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


galaxy = _script("migrate_168_galaxy_policies")
FIRST = list(uas.GALAXY_POLICIES)[:uas.GAME_CONFIG["GALAXY_POLICIES_PER_ROUND"]]

OLD = {
    "id": "galaxy_votes_1:1",
    "votes": {"policy_1": {"1": "1", "2": "2", "3": "1"}, "policy_2": {"1": "2", "4": "1"}, "leader": {"1": "1"}},
    "active_policies": ["Expansionist", "Conscription"],
    "policy_1_winner": "1", "policy_2_winner": "2", "leader": "1",
}


def test_an_old_round_writes_down_the_policies_it_already_plays():
    assert galaxy.plan_state({"game_start": "x"}) == {"galaxy_policies": FIRST}
    assert galaxy.plan_state({"galaxy_policies": ["arsenal"]}) == {}


def test_old_votes_become_votes_for_the_same_options_and_the_active_ones_stay():
    fields = galaxy.plan_galaxy(OLD, FIRST, NOW)
    assert fields["policy_votes"]["growth_doctrine"] == {"1": "expansionist", "3": "expansionist"}
    assert fields["policy_votes"]["tempo_doctrine"] == {"2": "warlike"}
    assert fields["policy_votes"]["defense_doctrine"] == {"1": "conscription", "4": "intelligence"}
    assert fields["policy_votes"]["research_focus"] == {}
    assert fields["policy_active"] == {"growth_doctrine": "expansionist", "defense_doctrine": "conscription"}
    assert fields["policy_updated"] == NOW.isoformat()


def test_a_moved_galaxy_reads_as_the_old_one_did_and_the_next_tally_counts_its_votes():
    moved = {**OLD, **galaxy.plan_galaxy(OLD, FIRST, NOW)}
    start = NOW - datetime.timedelta(days=3)
    assert gp.advance(moved, FIRST, start, NOW)["active"] == {"growth_doctrine": "expansionist", "defense_doctrine": "conscription"}
    after = gp.advance(moved, FIRST, start, NOW + datetime.timedelta(days=1))["active"]
    assert after == {"growth_doctrine": "expansionist", "tempo_doctrine": "warlike", "defense_doctrine": "conscription"}


def test_running_it_again_changes_nothing():
    moved = {**OLD, **galaxy.plan_galaxy(OLD, FIRST, NOW)}
    assert galaxy.plan_galaxy(moved, FIRST, NOW) == {}


def test_options_of_policies_the_round_does_not_play_are_left_out():
    fields = galaxy.plan_galaxy(OLD, ["growth_doctrine", "arsenal"], NOW)
    assert fields["policy_votes"] == {"growth_doctrine": {"1": "expansionist", "3": "expansionist"}, "arsenal": {}}
    assert fields["policy_active"] == {"growth_doctrine": "expansionist"}


cluster = _script("migrate_168_cluster_benefits")


def test_an_old_round_writes_down_the_cluster_benefits_it_already_plays():
    fields = cluster.plan_state({"game_start": "x"})
    assert fields == {"cluster_benefits": list(uas.CLUSTER_BENEFITS)[:uas.GAME_CONFIG["CLUSTER_BENEFITS_PER_ROUND"]]}
    assert fields["cluster_benefits"][:3] == ["drone_production", "unit_cost", "settle_cost"]
    assert cluster.plan_state({"cluster_benefits": ["pop_growth"]}) == {}
