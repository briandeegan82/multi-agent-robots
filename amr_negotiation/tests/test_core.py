from pathlib import Path

import pytest

from amr_negotiation import load_scenario, run_episode
from amr_negotiation.cli import apply_overrides, parse_set
from amr_negotiation.planner import Snapshot, best_plan, feasible
from amr_negotiation.policies import decide, decide_rulebook, load_rulebook
from amr_negotiation.sim2d import run_oracle

ROOT = Path(__file__).resolve().parent.parent
SINGLE = ROOT / "scenarios" / "corridor_single_bay.yaml"


@pytest.fixture
def sc():
    return load_scenario(SINGLE)


def snap(id, x, dir, entered=0.0, urgency=1.0, loaded=False, v=0.26):
    return Snapshot(
        id=id,
        t=10.0,
        x=x,
        dir=dir,
        v=v,
        goal_x=10.0 if dir > 0 else -2.0,
        entered_t=entered,
        urgency=urgency,
        loaded=loaded,
        v_max=0.26,
        v_rev_max=0.15,
        w_max=1.82,
        a_max=0.5,
    )


def test_geometry(sc):
    assert sc.circle_free(4.0, 0.0, sc.robot.radius)
    assert not sc.circle_free(2.0, 0.3, sc.robot.radius)  # corridor wall, no bay at x=2
    ids = {r.id for r in sc.refuges()}
    assert {"bay0", "room_lo", "room_hi"} <= ids
    # refuge parking spot must actually clear the corridor lane
    bay = next(r for r in sc.refuges() if r.id == "bay0")
    assert abs(bay.park_y) - sc.robot.radius >= sc.width / 2 - 1e-6
    assert sc.circle_free(bay.x, bay.park_y, sc.robot.radius)


def test_corridor_is_single_lane(sc):
    assert sc.width < 4 * sc.robot.radius


def test_bay_behind_feasible_bay_ahead_not(sc):
    bay = next(r for r in sc.refuges() if r.id == "bay0")
    a = snap("A", 3.0, +1)  # bay ahead of A by 1 m
    b = snap("B", 5.5, -1)  # bay ahead of B by 1.5 m
    assert feasible(bay, a, b, sc)
    a_past = snap("A", 5.0, +1)  # A already past the bay: it is behind A, A can reverse into it
    b_close = snap("B", 6.0, -1)
    assert feasible(bay, a_past, b_close, sc)
    plan = best_plan(a, b, sc)
    assert plan is not None and plan["refuge"] == "bay0"


def test_rulebook_first_in_corridor(sc):
    a, b = snap("A", 3.0, +1, entered=0.0), snap("B", 5.0, -1, entered=5.0)
    d = decide_rulebook([a, b], sc, load_rulebook(None))
    assert d.yielder == "B" and d.rule == "first_in_corridor"


def test_rulebook_urgency_and_loaded(sc):
    a, b = snap("A", 3.0, +1, entered=0.0), snap("B", 5.0, -1, entered=5.0, urgency=2.0)
    assert decide_rulebook([a, b], sc, load_rulebook(None)).yielder == "A"
    a, b = snap("A", 3.0, +1, entered=0.0, loaded=True), snap("B", 5.0, -1, entered=5.0)
    d = decide_rulebook([a, b], sc, load_rulebook(None))
    assert d.yielder == "B" and d.rule == "loaded"


def test_decision_is_symmetric(sc):
    a, b = snap("A", 3.2, +1, entered=1.0), snap("B", 5.1, -1, entered=1.3)
    for pol in ({"name": "rule_based"}, {"name": "cost_bid"}, {"name": "fixed_priority"}):
        d1, d2 = decide(pol, [a, b], sc), decide(pol, [b, a], sc)
        assert (d1.yielder, d1.refuge) == (d2.yielder, d2.refuge)


def test_lower_id_tiebreak(sc):
    a, b = snap("A", 3.0, +1), snap("B", 5.0, -1)
    rb = [{"rule": "lower_id_priority"}]
    assert decide_rulebook([a, b], sc, rb).yielder == "B"


def test_overrides(sc):
    sc2 = apply_overrides(sc, parse_set(["bays.0.x=2.5", "comms.loss=0.3", "width=0.7"]))
    assert sc2.bays[0]["x"] == 2.5 and sc2.comms["loss"] == 0.3 and sc2.width == 0.7
    assert sc.bays[0]["x"] == 4.0


@pytest.mark.parametrize("policy", ["reactive", "fixed_priority", "rule_based", "cost_bid"])
def test_episode_resolves_without_collision(sc, policy):
    r = run_episode(sc, {"name": policy}, seed=0)
    assert r["success"], r["events"]
    assert r["min_clearance"] > 0
    assert r["wall_hits"] == 0
    assert r["n_yields"] >= 1


def test_negotiation_beats_reactive_and_cost_bid_matches_oracle(sc):
    react = run_episode(sc, {"name": "reactive"}, seed=0)
    cb = run_episode(sc, {"name": "cost_bid"}, seed=0)
    orc = run_oracle(sc, seed=0)
    assert cb["total_delay"] < react["total_delay"]
    assert cb["total_delay"] <= orc["total_delay"] + 1.0
    assert cb["agreement"]


def test_rule_based_logs_rule_and_agrees(sc):
    r = run_episode(sc, {"name": "rule_based"}, seed=0)
    assert r["rule"] == "first_in_corridor" and r["yielder"] == "B" and r["agreement"]


def test_urgent_loaded_robot_keeps_right_of_way():
    sc = load_scenario(ROOT / "scenarios" / "corridor_urgent_loaded.yaml")
    r = run_episode(sc, {"name": "rule_based"}, seed=0)
    assert r["success"] and r["yielder"] == "A" and r["rule"] == "urgency"


def test_two_bays():
    sc = load_scenario(ROOT / "scenarios" / "corridor_two_bays.yaml")
    for pol in ("rule_based", "cost_bid"):
        assert run_episode(sc, {"name": pol}, seed=0)["success"]


def test_packet_loss_still_resolves(sc):
    sc2 = apply_overrides(sc, {"comms": {"loss": 0.5}})
    r = run_episode(sc2, {"name": "rule_based"}, seed=3)
    assert r["success"] and r["msgs_dropped"] > 0


def test_deterministic(sc):
    r1 = run_episode(sc, {"name": "cost_bid"}, seed=7)
    r2 = run_episode(sc, {"name": "cost_bid"}, seed=7)
    assert r1["makespan"] == r2["makespan"] and r1["yielder"] == r2["yielder"]


def test_gz_world_generation(sc, tmp_path):
    import xml.etree.ElementTree as ET

    from amr_negotiation import gzworld

    try:
        tpl = gzworld.find_waffle_sdf()
    except FileNotFoundError:
        pytest.skip("TurtleBot3 model not installed")
    w, _ = gzworld.write_world(sc, tmp_path, waffle_sdf=tpl)
    root = ET.parse(w).getroot()
    models = {m.get("name") for m in root.iter("model")}
    assert {"A", "B", "overhead_camera"} <= models
    assert "/A/cmd_vel" in w.read_text() and "camera/image_raw" not in w.read_text()
    for cx, cy, _, _ in gzworld.wall_boxes(sc):
        assert not gzworld._inside(sc, cx, cy)


def test_footprint_overlap():
    from amr_negotiation.geometry import RobotSpec, footprints_overlap

    fp = RobotSpec().footprint
    assert footprints_overlap((0, 0, 0), (0.1, 0, 3.1416), fp)
    assert not footprints_overlap((0, 0, 0), (0.2, 0, 3.1416), fp)  # head-on, fronts 4.7 cm apart
    assert not footprints_overlap((0, 0, 0), (0, 0.32, 0), fp)


def test_convoy_three_robots_resolves():
    """A two-robot convoy meeting one oncoming robot resolves with every negotiating policy."""
    from amr_negotiation import sim2d
    from amr_negotiation.geometry import load_scenario

    sc = load_scenario(Path(__file__).resolve().parents[1] / "scenarios/corridor_convoy.yaml")
    for pol in ({"name": "fixed_priority"}, {"name": "cost_bid"}):
        r = sim2d.run_episode(sc, pol, seed=0)
        assert r["success"], pol


def test_tjunction_stem_robot_joins():
    """A robot waiting in a T-junction stem joins the corridor past two head-on robots under every negotiating policy."""
    from amr_negotiation import sim2d
    from amr_negotiation.geometry import load_scenario

    sc = load_scenario(Path(__file__).resolve().parents[1] / "scenarios/corridor_tjunction.yaml")
    assert sc.start_pose(sc.agents[2])[1] < -sc.half_width
    for pol in ({"name": "fixed_priority"}, {"name": "cost_bid"}):
        r = sim2d.run_episode(sc, pol, seed=0)
        assert r["success"], pol


def test_lossy_extreme_comms_no_shared_bay():
    """At 90% loss / 8 s latency one robot falls back to reactive; the other must not follow it into the same bay."""
    from amr_negotiation import sim2d, sweep

    sc = sweep.apply_overrides(
        sweep.load_scenario(
            str(Path(__file__).resolve().parents[1] / "scenarios/corridor_single_bay.yaml")
        ),
        sweep._overrides(
            {
                "robot.v_max": 0.5,
                "comms.loss": 0.9,
                "comms.latency": 8.0,
                "agents.1.start_delay": 3.866,
            }
        ),
    )
    r = sim2d.run_episode(
        sc, {"name": "fixed_priority", "agent_params": {"detect_range": 6.0}}, seed=15
    )
    assert r["success"] and not r["collision"]


def test_asymmetric_map_share():
    """A knows no bays, B knows both: with share_map A learns them from B's BID and the robots agree."""
    from amr_negotiation import sim2d, sweep

    sc = sweep.load_scenario(str(Path(__file__).resolve().parents[1] / "scenarios/corridor_two_bays.yaml"))
    sc.agents[0].known_refuges = []
    own = sim2d.run_episode(sc, {"name": "fixed_priority"}, seed=0, record=True)
    shared = sim2d.run_episode(
        sc, {"name": "fixed_priority", "agent_params": {"share_map": True}}, seed=0, record=True
    )
    assert own["success"] and shared["success"] and not shared["collision"]
    assert not any(e["event"] == "decision_mismatch" for e in shared["events"])
    assert shared["total_delay"] < own["total_delay"]


def test_tjunction_goal_refuge():
    """A robot whose destination is the stem waits for the stem occupant to leave, then turns in."""
    from amr_negotiation import sim2d, sweep

    sc = sweep.load_scenario(
        str(Path(__file__).resolve().parents[1] / "scenarios/corridor_tjunction_goal.yaml")
    )
    r = sim2d.run_episode(sc, {"name": "cost_bid"}, seed=0, record=True)
    assert r["success"] and not r["collision"]
    assert any(
        e["agent"] == "A" and e["event"] == "goal_reached" and e.get("refuge") == "bay1"
        for e in r["events"]
    )


def test_blocked_bay_yielder_falls_back_instead_of_deadlocking():
    sc = load_scenario(ROOT / "scenarios" / "corridor_two_bays.yaml")
    sc.blocked_bays = ["bay1"]
    for pol in ("fixed_priority", "cost_bid"):
        r = run_episode(sc, {"name": pol}, seed=0, record=True)
        assert r["success"] and not r["collision"], pol
        assert any(e["event"] == "refuge_blocked" for e in r["events"]), pol


def test_learned_policy_uses_table_and_falls_back():
    sc = load_scenario(ROOT / "scenarios" / "corridor_two_bays.yaml")
    r0 = run_episode(sc, {"name": "learned", "table": {}}, seed=0)
    key = r0["decisions"][0]["features"]
    assert r0["success"] and r0["decisions"][0]["rule"] == "learned:fallback"
    r = run_episode(sc, {"name": "learned", "table": {key: {"a": [100.0, 1], "b": [1.0, 1]}}}, seed=0)
    assert r["success"] and {d["yielder"] for d in r["decisions"]} == {"B"}
    r = run_episode(sc, {"name": "learned", "table": {key: {"a": [1.0, 1], "b": [100.0, 1]}}}, seed=0)
    assert r["success"] and {d["yielder"] for d in r["decisions"]} == {"A"}


def test_scenario_goals_reachable_without_touching_room_walls():
    """A goal closer than radius + stop margin to an end wall is only reachable in 2D (no wall perception)."""
    for f in sorted((ROOT / "scenarios").glob("*.yaml")):
        sc = load_scenario(f)
        m = sc.robot.radius + 0.10 + 0.05
        for a in sc.agents:
            assert -sc.room_length + m <= a.goal_x <= sc.length + sc.room_length - m, (f.name, a.id, a.goal_x)


def test_lane_clear_uses_state_of_approaching_peer_when_lidar_is_occluded():
    """A robot deep in the stem cannot see the corridor; a fresh STATE of an approaching peer still blocks its exit."""
    from amr_negotiation.agent import Agent, Perception
    from amr_negotiation.planner import refuge_by_id

    sc = load_scenario(ROOT / "scenarios" / "corridor_tjunction.yaml")
    s = Agent(next(a for a in sc.agents if a.id == "S"), sc, {"name": "fixed_priority"})
    stem = refuge_by_id(sc, "bay1")
    s.peers["B"] = {"x": stem.x + 0.8, "y": 0.0, "v": -0.2, "dir": -1, "mode": "PROCEED", "_rx": 10.0}
    assert s.lane_clear(stem, Perception(), t=None)
    assert not s.lane_clear(stem, Perception(), t=10.0)
    s.peers["B"].update(x=stem.x - 0.8)  # already past the stem
    assert s.lane_clear(stem, Perception(), t=10.0)


def test_group_bid_matches_cost_bid_for_pairs_and_counts_convoy():
    from amr_negotiation.policies import decide_cost_bid, decide_group_bid

    sc = load_scenario(ROOT / "scenarios" / "corridor_convoy.yaml")
    mk = lambda i, x, d, g: Snapshot(i, 0.0, x, d, 0.26, 12.8 if d > 0 else -2.0, None, 1.0, False,
                                     0.26, 0.15, 1.8, 0.5, group=g)
    a, b = mk("A", 1.0, 1, None), mk("B", 6.0, -1, None)
    assert decide_group_bid([a, b], sc).yielder == decide_cost_bid([a, b], sc).yielder
    a2 = mk("A", 1.0, 1, [mk("C", -0.2, 1, None)])
    d = decide_group_bid([a2, b], sc)
    assert d.yielder == "B" and d.detail["groups"]["A"] == ["C"]
    assert Snapshot.from_dict(a2.to_dict()).group[0].id == "C"


def test_convoy_follower_makes_room_for_yielding_leader():
    sc = apply_overrides(load_scenario(ROOT / "scenarios" / "corridor_convoy.yaml"),
                         parse_set(["bays.0.x=2.0", "bays.1.x=8.0", "agents.2.start_delay=4.0", "agents.2.urgency=3.0"]))
    for pol in ("cost_bid", "group_bid"):
        r = run_episode(sc, {"name": pol}, seed=0)
        assert r["success"] and not r["collision"], pol


def test_tjunction_goal_waits_in_bay_for_stem_exit():
    """Stem occupant leaving towards a robot whose destination is the stem: no deadlock."""
    from amr_negotiation import sweep as SW

    for goal_x, sd_b in ((-1.5, 0.0), (10.0, 8.0)):
        sc = SW.apply_overrides(
            load_scenario(ROOT / "scenarios" / "corridor_tjunction_goal.yaml"),
            SW._overrides({"agents.0.start_delay": 0.0, "agents.1.start_delay": sd_b,
                           "agents.2.start_delay": 0.0, "agents.2.goal_x": goal_x, "comms.loss": 0.0}),
        )
        for pol in ("fixed_priority", "rule_based", "cost_bid"):
            spec = {"name": pol}
            if pol == "rule_based":
                spec["rulebook"] = str(ROOT / "rulebooks" / "default.yaml")
            r = run_episode(sc, spec, seed=0)
            assert r["success"] and not r["collision"], (goal_x, sd_b, pol)


def test_bids_weight_each_delay_by_its_owners_urgency():
    from amr_negotiation.planner import best_plan
    from amr_negotiation.policies import group_yield_cost, yield_bid

    sc = load_scenario(ROOT / "scenarios" / "corridor_convoy.yaml")
    mk = lambda i, x, d, u, g=None: Snapshot(i, 0.0, x, d, 0.26, 12.8 if d > 0 else -2.0, None, u, False,
                                             0.26, 0.15, 1.8, 0.5, group=g)
    a, b = mk("A", 1.0, 1, 1.0), mk("B", 6.0, -1, 3.0)
    p = best_plan(a, b, sc)
    assert yield_bid(a, b, sc) == pytest.approx(1.0 * p["yielder_delay"] + 3.0 * p["proceeder_delay"])
    assert group_yield_cost(a, b, sc) == pytest.approx(yield_bid(a, b, sc))


def test_clarke_pivot_is_second_price_and_truthful():
    import itertools
    import random

    from amr_negotiation.mechanism import clarke

    # A yields: costs 10 + 1 = 11. B yields: 2 + 4 = 6, so B yields; A pays 4 - min(1, 4) = 3.
    y, pay = clarke({"A": {"A": 10.0, "B": 1.0}, "B": {"A": 2.0, "B": 4.0}})
    assert y == "B" and pay == {"A": pytest.approx(3.0), "B": pytest.approx(0.0)}
    rng = random.Random(0)
    for _ in range(300):
        true = {o: {i: rng.uniform(0, 30) for i in "AB"} for o in "AB"}
        y, pay = clarke(true)
        for i, k in itertools.product("AB", (0.1, 0.5, 0.9, 1.1, 2.0, 10.0)):
            rep = {o: {j: c * (k if j == i else 1.0) for j, c in v.items()} for o, v in true.items()}
            y2, pay2 = clarke(rep)
            assert true[y2][i] + pay2[i] >= true[y][i] + pay[i] - 1e-9
        assert min(pay.values()) >= 0.0


def test_truthful_clarke_matches_cost_bid_for_symmetric_robots():
    sc = load_scenario(ROOT / "scenarios" / "corridor_single_bay.yaml")
    for seed in range(3):
        rc = run_episode(sc, {"name": "clarke"}, seed=seed)
        rb = run_episode(sc, {"name": "cost_bid"}, seed=seed)
        assert rc["success"] and rc.get("yielder") == rb.get("yielder")
        assert all(v >= 0 for v in rc["decisions"][0]["payments"].values())


def test_reservation_waits_outside_while_corridor_is_held():
    sc = apply_overrides(load_scenario(ROOT / "scenarios" / "corridor_single_bay.yaml"),
                         parse_set(["agents.1.start_delay=5.0"]))
    r = run_episode(sc, {"name": "reservation"}, seed=0)
    assert r["success"] and not r["collision"]
    assert r["yielder"] == "B" and r["rule"] == "reservation" and r["refuge"] == "room_hi"


def test_explore_mode_learns_bays_by_sensing_and_shares_only_after_detection():
    sc = load_scenario(ROOT / "scenarios" / "corridor_two_bays.yaml")
    sc.agent_params = {"explore": True, "share_map": True, "share_on_detect": True}
    r = run_episode(sc, {"name": "fixed_priority"}, seed=0, record=True)
    assert r["success"] and not r["collision"]
    ev = r["events"]
    sensed = [e for e in ev if e["event"] == "refuge_learned" and e["source"] == "sensed"]
    assert {e["agent"] for e in sensed} == {"A", "B"}
    det = {(e["agent"], e["peer"]): e["t"] for e in ev if e["event"] == "peer_detected"}
    shared = [e for e in ev if e["event"] == "refuge_learned" and e["source"] != "sensed"]
    assert shared and all(e["t"] >= det[(e["source"], e["agent"])] for e in shared)
    sc.agent_params = {}
    full = run_episode(sc, {"name": "fixed_priority"}, seed=0, record=True)
    assert not any(e["event"] == "refuge_learned" for e in full["events"])


def _explore_run(seed=0, **params):
    sc = load_scenario(ROOT / "scenarios" / "corridor_two_bays.yaml")
    sc.agent_params = {"explore": True, "share_map": True, "detect_range": 6.0, **params}
    return run_episode(sc, {"name": "fixed_priority"}, seed=seed, record=True)


def _key(r):
    return r["success"], r["collision"], r["total_delay"], [(d["t"], d["agent"], d["yielder"]) for d in r["decisions"]]


def test_hold_for_map_is_off_by_default_and_needs_share_on_detect():
    from amr_negotiation.agent import AgentParams
    assert AgentParams().hold_for_map is False
    r = _explore_run(share_on_detect=True)
    det = {(e["agent"], e["peer"]): e["t"] for e in r["events"] if e["event"] == "peer_detected"}
    assert r["decisions"][0]["t"] < min(det.values())  # current behaviour: decide on the radio, before sensing
    assert _key(_explore_run(hold_for_map=True)) == _key(_explore_run())  # share every BID: flag has no effect


def test_hold_for_map_decides_after_detection_and_map_exchange():
    r = _explore_run(share_on_detect=True, hold_for_map=True)
    assert r["success"] and not r["collision"]
    ev = r["events"]
    assert not any(e["event"] == "hold_timeout" for e in ev)
    det = {(e["agent"], e["peer"]): e["t"] for e in ev if e["event"] == "peer_detected"}
    for d in r["decisions"]:
        assert d["t"] >= det[(d["agent"], d["peer"])] and d["t"] >= det[(d["peer"], d["agent"])]
    no_hold = _explore_run(share_on_detect=True)
    assert r["total_delay"] < no_hold["total_delay"]


def test_hold_for_map_survives_a_lost_map_message():
    from amr_negotiation.cli import apply_overrides, parse_set
    sc = apply_overrides(load_scenario(ROOT / "scenarios" / "corridor_two_bays.yaml"), parse_set(["comms.loss=0.5"]))
    sc.agent_params = {"explore": True, "share_map": True, "share_on_detect": True, "hold_for_map": True}
    for seed in range(5):
        r = run_episode(sc, {"name": "fixed_priority"}, seed=seed, record=True)
        assert r["success"] and not r["collision"]
        assert not any(e["event"] == "hold_timeout" for e in r["events"])  # BIDs repeat the map after detection


def test_hold_for_map_timeout_falls_back_to_current_behaviour():
    r = _explore_run(share_on_detect=True, hold_for_map=True, hold_timeout=0.0)
    assert any(e["event"] == "hold_timeout" for e in r["events"])
    assert _key(r) == _key(_explore_run(share_on_detect=True))


def test_gazebo_world_has_obstacle_in_blocked_bay():
    from amr_negotiation import gzworld
    sc = load_scenario(ROOT / "scenarios" / "corridor_two_bays.yaml")
    assert gzworld.blocked_bay_poses(sc) == []
    sc.blocked_bays = ["bay1"]
    (x, y), = gzworld.blocked_bay_poses(sc)
    assert x == 7.0 and y < -sc.half_width
    try:
        sdf = gzworld.build_world(sc)
    except FileNotFoundError:
        pytest.skip("TurtleBot3 waffle model not installed")
    assert "obstacle_7.00" in sdf


def test_noise_episode_key_ignores_snapshot_time():
    from dataclasses import replace

    from amr_negotiation.policies import noisy
    a = snap("A", 1.0, 1)
    late = replace(a, t=a.t + 0.37)
    assert noisy(10.0, a, 0.5, 3, "episode") == noisy(10.0, late, 0.5, 3, "episode")
    assert noisy(10.0, a, 0.5, 3, "time") != noisy(10.0, late, 0.5, 3, "time")
    assert noisy(10.0, a, 0.5, 3, "episode") != noisy(10.0, a, 0.5, 4, "episode")
