"""Decision functions: given both robots' frozen snapshots, who yields and where.

Every function is deterministic in (snapshots, scenario, config), so each robot can evaluate it
locally once it holds both snapshots; no third message is needed to agree on the outcome.
"""

from __future__ import annotations

import json
import math
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from .geometry import Scenario
from .planner import Snapshot, best_plan, feasible, plan_times, refuge_by_id

NEGOTIATING_POLICIES = ("fixed_priority", "rule_based", "cost_bid", "group_bid", "learned", "clarke", "reservation", "forced", "llm")
ALL_POLICIES = ("reactive",) + NEGOTIATING_POLICIES


@dataclass
class Decision:
    yielder: str | None
    proceeder: str | None
    refuge: str | None
    rule: str
    detail: dict = field(default_factory=dict)


def _pair(snaps: list[Snapshot]) -> tuple[Snapshot, Snapshot]:
    a, b = sorted(snaps, key=lambda s: s.id)
    return a, b


def _finish(Y: Snapshot, P: Snapshot, sc: Scenario, rule: str, detail: dict | None = None) -> Decision:
    plan = best_plan(Y, P, sc)
    if plan is None:
        return Decision(None, None, None, rule + ":infeasible", detail or {})
    return Decision(Y.id, P.id, plan["refuge"], rule, {**(detail or {}), "plan": plan})


# ---------------------------------------------------------------- rule-based negotiation

def _other(a: Snapshot, b: Snapshot, s: Snapshot) -> Snapshot:
    return b if s is a else a


def rule_no_refuge(a, b, sc, **_):
    pa, pb = best_plan(a, b, sc), best_plan(b, a, sc)
    if pa is not None and pb is None:
        return a
    if pb is not None and pa is None:
        return b
    return None


def rule_urgency(a, b, sc, threshold: float = 0.5, **_):
    if abs(a.urgency - b.urgency) >= threshold:
        return a if a.urgency < b.urgency else b
    return None


def rule_loaded(a, b, sc, **_):
    if a.loaded != b.loaded:
        return b if a.loaded else a
    return None


def rule_first_in_corridor(a, b, sc, min_gap: float = 1.0, **_):
    ea, eb = a.entered_t, b.entered_t
    if ea is None and eb is None:
        return None
    if ea is None:
        return a
    if eb is None:
        return b
    if abs(ea - eb) >= min_gap:
        return a if ea > eb else b
    return None


def _refuge_behind_dist(Y: Snapshot, P: Snapshot, sc: Scenario) -> float | None:
    ds = [abs(r.x - Y.x) for r in sc.refuges()
          if Y.dir * (r.x - Y.x) <= 0 and feasible(r, Y, P, sc)]
    return min(ds) if ds else None


def rule_refuge_behind_within(a, b, sc, distance: float = 2.0, **_):
    da, db = _refuge_behind_dist(a, b, sc), _refuge_behind_dist(b, a, sc)
    ok_a = da is not None and da <= distance
    ok_b = db is not None and db <= distance
    if ok_a and not ok_b:
        return a
    if ok_b and not ok_a:
        return b
    return None


def rule_closest_refuge(a, b, sc, tie: float = 0.1, **_):
    pa, pb = best_plan(a, b, sc, "refuge_dist"), best_plan(b, a, sc, "refuge_dist")
    if pa is None or pb is None:
        return None
    if abs(pa["refuge_dist"] - pb["refuge_dist"]) < tie:
        return None
    return a if pa["refuge_dist"] < pb["refuge_dist"] else b


def rule_lower_id_priority(a, b, sc, **_):
    return b


RULES = {
    "no_refuge": rule_no_refuge,
    "urgency": rule_urgency,
    "loaded": rule_loaded,
    "first_in_corridor": rule_first_in_corridor,
    "refuge_behind_within": rule_refuge_behind_within,
    "closest_refuge": rule_closest_refuge,
    "lower_id_priority": rule_lower_id_priority,
}

FIXED_PRIORITY_RULEBOOK = [{"rule": "lower_id_priority"}]


def load_rulebook(spec) -> list[dict]:
    if spec is None:
        spec = Path(__file__).resolve().parent.parent / "rulebooks" / "default.yaml"
    if isinstance(spec, (str, Path)):
        spec = yaml.safe_load(Path(spec).read_text())["rules"]
    for r in spec:
        if r["rule"] not in RULES:
            raise KeyError(f"unknown rule {r['rule']!r}; known: {sorted(RULES)}")
    return spec


def decide_rulebook(snaps, sc, rulebook: list[dict]) -> Decision:
    a, b = _pair(snaps)
    for entry in rulebook:
        params = {k: v for k, v in entry.items() if k != "rule"}
        Y = RULES[entry["rule"]](a, b, sc, **params)
        if Y is not None:
            return _finish(Y, _other(a, b, Y), sc, entry["rule"])
    return _finish(b, a, sc, "default:lower_id_priority")


# ---------------------------------------------------------------- cost-based bidding

def yield_bid(Y: Snapshot, P: Snapshot, sc: Scenario, objective: str = "total_delay") -> float:
    """Predicted social cost of Y yielding to P; infinite if Y has no feasible refuge.

    For total delay each robot's delay is weighted by its own urgency: u_Y d_Y + u_P d_P."""
    plan = best_plan(Y, P, sc, objective)
    if plan is None:
        return float("inf")
    return plan["weighted_delay"] if objective == "total_delay" else plan[objective]


def noisy(bid: float, Y: Snapshot, sigma: float, seed: int) -> float:
    """Log-normal estimate error on a bid, fixed per (seed, robot, time to 0.1 s) so both robots see the same value."""
    if sigma <= 0 or not math.isfinite(bid):
        return bid
    h = zlib.crc32(f"{seed}|{Y.id}|{round(Y.t, 1)}".encode())
    return bid * math.exp(sigma * np.random.default_rng(h).standard_normal())


def decide_cost_bid(snaps, sc, objective: str = "total_delay", bid_sigma: float = 0.0, noise_seed: int = 0) -> Decision:
    a, b = _pair(snaps)
    ba, bb = yield_bid(a, b, sc, objective), yield_bid(b, a, sc, objective)
    ba, bb = noisy(ba, a, bid_sigma, noise_seed), noisy(bb, b, bid_sigma, noise_seed)
    detail = {"bids": {a.id: ba, b.id: bb}}
    if ba == float("inf") and bb == float("inf"):
        return Decision(None, None, None, "cost_bid:infeasible", detail)
    Y = a if ba < bb else b  # tie: b (higher id) yields
    return _finish(Y, _other(a, b, Y), sc, "cost_bid", detail)


# ---------------------------------------------------------------- learned (tabular, trained in the 2D sim)

_BINS = (1.0, 2.5, 5.0)


def learned_features(a: Snapshot, b: Snapshot, sc: Scenario) -> str:
    """Coarse, planner-free observation: per robot, binned distance to the nearest feasible refuge behind it
    (4 = none), plus urgency order and payload flags. Shared by both robots, so they compute the same key."""
    def behind(Y, P):
        ds = [Y.dir * (Y.x - r.x) for r in sc.refuges() if Y.dir * (Y.x - r.x) > -0.05 and feasible(r, Y, P, sc)]
        return 4 if not ds else sum(min(ds) > t for t in _BINS)
    u = (a.urgency > b.urgency) - (a.urgency < b.urgency)
    return f"{behind(a, b)}|{behind(b, a)}|{u}|{int(a.loaded)}|{int(b.loaded)}"


def decide_learned(snaps, sc, table: dict | str | None) -> Decision:
    """Yield the side with the lower learned mean cost; unseen observations fall back to fixed priority."""
    a, b = _pair(snaps)
    if isinstance(table, str):
        with open(table) as f:
            table = json.load(f)
    key = learned_features(a, b, sc)
    q = (table or {}).get(key)
    detail = {"features": key}
    if not q or not all(q.get(k, [0, 0])[1] for k in ("a", "b")):
        return _finish(b, a, sc, "learned:fallback", detail)
    ca, cb = (q[k][0] / q[k][1] for k in ("a", "b"))
    detail["q"] = {a.id: ca, b.id: cb}
    Y = a if ca < cb else b
    return _finish(Y, _other(a, b, Y), sc, "learned", detail)


def group_yield_cost(Y: Snapshot, P: Snapshot, sc: Scenario, objective: str = "total_delay") -> float:
    """Predicted urgency-weighted delay when Y's whole group (Y and its followers) makes way for P's group.

    Each member of Y's group needs its own bay (rooms can be shared) and also waits for P's followers to
    pass. P is held until the slowest member has parked; that delay is counted once and applies to P and
    each of its followers. With no followers on either side this equals `yield_bid`."""
    used: set[str] = set()
    yield_cost, p_delay = 0.0, 0.0
    for y in [Y, *(Y.group or [])]:
        plans = [plan_times(r, y, P, sc) for r in sc.refuges()
                 if r.id not in used and feasible(r, y, P, sc)]
        if not plans:
            return float("inf")
        plan = min(plans, key=lambda q: (q[objective], q["refuge_dist"]))
        if refuge_by_id(sc, plan["refuge"]).kind == "bay":
            used.add(plan["refuge"])
        if objective != "total_delay":
            yield_cost = max(yield_cost, plan[objective])
            continue
        yield_cost += y.urgency * plan["yielder_delay"]
        p_delay = max(p_delay, plan["proceeder_delay"])
    if objective != "total_delay":
        return yield_cost
    wait = max((abs(f.x - P.x) / f.v_max for f in P.group or []), default=0.0)
    yielders, proceeders = [Y, *(Y.group or [])], [P, *(P.group or [])]
    return yield_cost + wait * sum(y.urgency for y in yielders) + p_delay * sum(p.urgency for p in proceeders)


def decide_group_bid(snaps, sc, objective: str = "total_delay") -> Decision:
    a, b = _pair(snaps)
    ba, bb = group_yield_cost(a, b, sc, objective), group_yield_cost(b, a, sc, objective)
    detail = {"bids": {a.id: ba, b.id: bb},
              "groups": {a.id: [g.id for g in a.group or []], b.id: [g.id for g in b.group or []]}}
    if ba == float("inf") and bb == float("inf"):
        return Decision(None, None, None, "group_bid:infeasible", detail)
    Y = a if ba < bb else b  # tie: b (higher id) yields
    return _finish(Y, _other(a, b, Y), sc, "group_bid", detail)


# ---------------------------------------------------------------- Clarke-pivot mechanism

def decide_clarke(snaps, sc, report_scale: dict | None = None, report_urgency: dict | None = None) -> Decision:
    """Clarke-pivot choice of yielder (misreport studies below).

    `report_scale[i]` multiplies robot i's reported costs: a number scales both outcomes, a dict {outcome: k}
    scales each outcome independently. `report_urgency[i]` replaces robot i's private urgency in the reports
    (the reports are recomputed from the altered snapshot; `types` keeps the true costs)."""
    from dataclasses import replace

    from .mechanism import clarke, types

    a, b = _pair(snaps)
    true = types(a, b, sc)
    ru = report_urgency or {}
    base = types(*(replace(s, urgency=ru[s.id]) if s.id in ru else s for s in (a, b)), sc) if ru else true

    def k(i, o):
        v = (report_scale or {}).get(i, 1.0)
        return v.get(o, 1.0) if isinstance(v, dict) else v
    rep = {o: {i: c * k(i, o) for i, c in v.items()} for o, v in base.items()}
    y, pay = clarke(rep)
    detail = {"types": true, "reports": rep, "payments": pay}
    if y is None:
        return Decision(None, None, None, "clarke:infeasible", detail)
    Y = a if y == a.id else b
    return _finish(Y, _other(a, b, Y), sc, "clarke", detail)


# ---------------------------------------------------------------- dispatcher

def decide(policy: dict, snaps: list[Snapshot], sc: Scenario) -> Decision:
    name = policy["name"]
    if name == "fixed_priority":
        return decide_rulebook(snaps, sc, FIXED_PRIORITY_RULEBOOK)
    if name in ("rule_based", "reservation"):  # reservation falls back to the rulebook once both are inside
        return decide_rulebook(snaps, sc, load_rulebook(policy.get("rulebook")))
    if name == "cost_bid":
        return decide_cost_bid(snaps, sc, policy.get("objective", "total_delay"), policy.get("bid_sigma", 0.0),
                               policy.get("noise_seed", 0))
    if name == "learned":
        return decide_learned(snaps, sc, policy.get("table"))
    if name == "clarke":
        return decide_clarke(snaps, sc, policy.get("report_scale"), policy.get("report_urgency"))
    if name == "group_bid":
        return decide_group_bid(snaps, sc, policy.get("objective", "total_delay"))
    if name == "llm":
        from .llm import decide_llm

        return decide_llm(snaps, sc, policy)
    if name == "forced":
        a, b = _pair(snaps)
        Y = a if a.id == policy["yielder"] else b
        return _finish(Y, _other(a, b, Y), sc, "forced")
    raise ValueError(f"policy {name!r} does not negotiate")


def refuge_of(decision: Decision, sc: Scenario):
    return None if decision.refuge is None else refuge_by_id(sc, decision.refuge)
