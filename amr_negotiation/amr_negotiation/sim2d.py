"""Fast 2D unicycle simulator for Monte Carlo runs of the corridor negotiation scenarios."""

from __future__ import annotations

import copy
import json
import math
from dataclasses import asdict
from functools import lru_cache

import numpy as np

from .agent import Agent, Perception
from .geometry import Scenario, footprints_overlap, scenario_from_dict


def _circle_points(x, y, r, n=24):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.stack([x + r * np.cos(a), y + r * np.sin(a)], axis=1)


class Bus:
    """Broadcast channel with fixed latency, uniform jitter and per-receiver loss.

    Loss is independent per message (`loss`) unless `burst` is given: a Gilbert–Elliott chain per receiver,
    stepped once per message, with transition probabilities `p_gb` (good→bad) and `p_bg` (bad→good) and loss
    probabilities `loss_good` / `loss_bad`. `blackout: [t0, t1]` drops every message sent in that window."""

    def __init__(self, comms: dict, rng: np.random.Generator):
        self.latency = comms.get("latency", 0.05)
        self.jitter = comms.get("jitter", 0.0)
        self.loss = comms.get("loss", 0.0)
        self.burst = comms.get("burst")
        self.blackout = comms.get("blackout")
        self.bad: dict[str, bool] = {}
        self.rng = rng
        self.queue: list[tuple[float, str, dict]] = []
        self.sent = 0
        self.dropped = 0

    def _lost(self, t, rcv) -> bool:
        if self.blackout and self.blackout[0] <= t < self.blackout[1]:
            return True
        if not self.burst:
            return self.rng.random() < self.loss
        b = self.burst
        bad = self.bad.get(rcv, False)
        bad = self.rng.random() >= b["p_bg"] if bad else self.rng.random() < b["p_gb"]
        self.bad[rcv] = bad
        return self.rng.random() < (b.get("loss_bad", 1.0) if bad else b.get("loss_good", 0.0))

    def send(self, t, msg, receivers):
        for rcv in receivers:
            self.sent += 1
            if self._lost(t, rcv):
                self.dropped += 1
                continue
            self.queue.append((t + self.latency + self.jitter * self.rng.random(), rcv, msg))

    def deliver(self, t, rcv):
        out = [m for (tt, r, m) in self.queue if r == rcv and tt <= t + 1e-9]
        self.queue = [(tt, r, m) for (tt, r, m) in self.queue if not (r == rcv and tt <= t + 1e-9)]
        return out


def scenario_to_dict(sc: Scenario) -> dict:
    d = asdict(sc)
    return d


@lru_cache(maxsize=4096)
def _free_flow_time(sc_json: str, agent_id: str) -> float:
    d = json.loads(sc_json)
    d["agents"] = [a for a in d["agents"] if a["id"] == agent_id]
    for a in d["agents"]:
        a["start_delay"] = 0.0
    sc = scenario_from_dict(d)
    res = run_episode(sc, {"name": "reactive"}, seed=0, free_flow=False)
    return res["agents"][agent_id]["travel_time"]


def free_flow_time(sc: Scenario, agent_id: str) -> float:
    return _free_flow_time(json.dumps(scenario_to_dict(sc), sort_keys=True), agent_id)


def run_episode(sc: Scenario, policy: dict, seed: int = 0, record: bool = False,
                free_flow: bool = True, record_every: int = 2) -> dict:
    rng = np.random.default_rng(seed)
    sc = copy.deepcopy(sc)
    rs = sc.robot
    agents = {a.id: Agent(a, sc, policy, rng=np.random.default_rng(rng.integers(1 << 31))) for a in sc.agents}
    st = {a.id: np.array([*sc.start_pose(a), 0.0, 0.0]) for a in sc.agents}
    bus = Bus(sc.comms, np.random.default_rng(rng.integers(1 << 31)))
    ids = list(agents)
    dt, t = sc.dt, 0.0
    min_dist = float("inf")
    collision_t = None
    obstacles = [(r.x, r.park_y) for r in sc.refuges() if r.id in set(sc.blocked_bays)]
    wall_hits = 0
    reverse = {i: 0.0 for i in ids}
    trace = []
    step = 0
    while t <= sc.t_max:
        cmds = {}
        for i in ids:
            s = st[i]
            pts, peers = [], []
            for j in ids:
                if j == i or (sc.despawn_done and agents[j].mode == "DONE"):
                    continue
                o = st[j]
                if math.hypot(o[0] - s[0], o[1] - s[1]) <= rs.lidar_range:
                    pts.append(_circle_points(o[0], o[1], rs.radius))
                    peers.append((float(o[0]), float(o[1])))
            for ox, oy in obstacles:
                if math.hypot(ox - s[0], oy - s[1]) <= rs.lidar_range:
                    pts.append(_circle_points(ox, oy, rs.radius))
                    peers.append((ox, oy))
            perc = Perception(np.concatenate(pts) if pts else np.zeros((0, 2)), peers)
            pose = (float(s[0]), float(s[1]), float(s[2]), float(s[3]))
            v, w, out = agents[i].step(t, pose, perc, bus.deliver(t, i))
            for m in out:
                bus.send(t, m, [j for j in ids if j != i])
            cmds[i] = (v, w)
        for i in ids:
            s = st[i]
            v_cmd, w_cmd = cmds[i]
            s[3] += np.clip(v_cmd - s[3], -rs.a_max * dt, rs.a_max * dt)
            s[4] += np.clip(w_cmd - s[4], -rs.alpha_max * dt, rs.alpha_max * dt)
            s[4] = np.clip(s[4], -rs.w_max, rs.w_max)
            s[0] += s[3] * math.cos(s[2]) * dt
            s[1] += s[3] * math.sin(s[2]) * dt
            s[2] = (s[2] + s[4] * dt + math.pi) % (2 * math.pi) - math.pi
            if s[3] < 0:
                reverse[i] += -s[3] * dt
            if step % 10 == 0 and not sc.circle_free(s[0], s[1], 0.15):
                wall_hits += 1
        for a_i in range(len(ids)):
            for b_i in range(a_i + 1, len(ids)):
                if sc.despawn_done and "DONE" in (agents[ids[a_i]].mode, agents[ids[b_i]].mode):
                    continue
                p, q = st[ids[a_i]], st[ids[b_i]]
                d = math.hypot(p[0] - q[0], p[1] - q[1])
                min_dist = min(min_dist, d)
                if collision_t is None and d < 0.6 and footprints_overlap(p, q, rs.footprint):
                    collision_t = t
        for i in ids:
            if collision_t is None and not (sc.despawn_done and agents[i].mode == "DONE") and any(
                    math.hypot(st[i][0] - ox, st[i][1] - oy) < 2 * rs.radius for ox, oy in obstacles):
                collision_t = t
        if record and step % record_every == 0:
            trace.append({"t": round(t, 3), **{i: [round(float(v), 4) for v in st[i][:4]] + [agents[i].mode, agents[i].phase]
                                                for i in ids}})
        if all(agents[i].mode == "DONE" for i in ids):
            break
        t += dt
        step += 1
    res_agents = {}
    for i in ids:
        a = agents[i]
        travel = (a.done_t - a.cfg.start_delay) if a.done_t is not None else None
        res_agents[i] = {"done": a.done_t is not None, "arrival": a.done_t, "travel_time": travel,
                         "reverse_dist": reverse[i], "yields": a.n_yields, "msgs_sent": a.msgs_sent}
    all_done = all(r["done"] for r in res_agents.values())
    out = {
        "policy": policy["name"], "seed": seed, "success": all_done and collision_t is None,
        "all_done": all_done, "deadlock": not all_done, "collision": collision_t is not None,
        "wall_hits": wall_hits, "min_clearance": min_dist - 2 * rs.radius if len(ids) > 1 else None,
        "makespan": max((r["arrival"] or float("nan")) for r in res_agents.values()) if all_done else None,
        "agents": res_agents, "msgs": bus.sent, "msgs_dropped": bus.dropped,
        "events": sorted((e for a in agents.values() for e in a.events), key=lambda e: e["t"]),
        "decisions": [d for a in agents.values() for d in a.decisions],
    }
    if free_flow and all_done:
        delays = {i: res_agents[i]["travel_time"] - free_flow_time(sc, i) for i in ids}
        for i in ids:
            res_agents[i]["delay"] = delays[i]
        out["total_delay"] = sum(delays.values())
        out["max_delay"] = max(delays.values())
    dec = out["decisions"]
    if dec:
        out["yielder"] = dec[0]["yielder"]
        out["rule"] = dec[0]["rule"]
        out["refuge"] = dec[0]["refuge"]
        out["time_to_decide"] = min(d["t"] - d["t_detect"] for d in dec)
        out["agreement"] = len({(d["yielder"], d["refuge"]) for d in dec if d["peer"]}) == 1
    else:
        ys = [e for e in out["events"] if e["event"] == "yield_start"]
        out["yielder"] = ys[0]["agent"] if ys else None
        out["rule"] = ys[0]["rule"] if ys else None
        out["refuge"] = ys[0]["refuge"] if ys else None
    out["n_yields"] = sum(r["yields"] for r in res_agents.values())
    if record:
        out["trace"] = trace
    return out


def run_oracle(sc: Scenario, seed: int = 0, objective: str = "total_delay", record=False) -> dict:
    """Centralised hindsight baseline: simulate each forced yielder and keep the better outcome."""
    best = None
    for a in sc.agents:
        r = run_episode(sc, {"name": "forced", "yielder": a.id}, seed=seed, record=record)
        key = r.get(objective) if r["success"] else float("inf")
        if best is None or (key if key is not None else float("inf")) < best[0]:
            best = (key if key is not None else float("inf"), r)
    res = best[1]
    res["policy"] = "oracle"
    return res
