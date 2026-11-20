"""Simulator-agnostic negotiating agent (one per robot).

The same class drives the robot in the fast 2D simulator and inside the ROS 2 / Gazebo node.
Each control tick the host passes the robot pose, perceived obstacles (world-frame points and
peer position estimates) and received messages; the agent returns (v, w) and outgoing messages.
Messages are plain JSON-serialisable dicts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .geometry import AgentConfig, Refuge, Scenario
from .planner import Snapshot, hold_x, pass_x, refuge_by_id
from .policies import NEGOTIATING_POLICIES, Decision, decide, refuge_of


def wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


@dataclass
class Perception:
    points: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    peers: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class AgentParams:
    detect_range: float = 6.0
    neg_period: float = 0.3
    neg_timeout: float = 3.0
    share_map: bool = False  # BIDs carry the sender's known bays; the receiver adds them before deciding
    share_on_detect: bool = False  # with share_map: send our map only once our own sensor has detected that robot
    hold_for_map: bool = False  # with share_on_detect: keep driving, undecided, until our sensor has detected the
    # peer and its MAP has arrived (or hold_timeout), so the decision uses the exchanged maps
    hold_timeout: float = 15.0
    explore: bool = False  # start without bays (unless known_refuges is given) and add each bay once it is within lidar range
    commit: bool = True  # wait for the peer's decision (or neg_timeout) before acting; False: act on our own at once
    state_guard: bool = True  # STATE messages expose a peer yielding into our bay / to us, and we proceed instead
    bay_check: bool = True  # lidar-occupied bays count as taken, and a yielder that senses one in its bay proceeds
    state_timeout: float = 1.0
    stop_margin: float = 0.10
    lateral_margin: float = 0.03
    patience: tuple[float, float] = (2.0, 6.0)
    park_timeout: tuple[float, float] = (6.0, 12.0)
    proceed_timeout: float = 60.0
    lane_lookahead: float = 0.4
    k_heading: float = 2.5
    k_dist: float = 1.5
    goal_tol: float = 0.05


class Agent:
    def __init__(self, cfg: AgentConfig, sc: Scenario, policy: dict, rng: np.random.Generator | None = None,
                 params: AgentParams | None = None):
        self.cfg, self.sc, self.policy = cfg, sc, dict(policy)
        self.p = params or AgentParams(**{**getattr(sc, "agent_params", {}), **policy.get("agent_params", {})})
        self.rng = rng or np.random.default_rng()
        self.id, self.dir, self.goal_x = cfg.id, cfg.direction, cfg.goal_x
        known = cfg.known_refuges
        if known is None and self.p.explore:
            known = []
        self.unknown = set() if known is None else {
            r.id for r in sc.refuges() if r.kind == "bay" and r.id not in known}
        self.detected: set[str] = set()  # peers our own sensor has seen (not just heard on the radio)
        self.map_from: set[str] = set()  # peers whose MAP message we have received
        self.obstructed: set[str] = set()  # bays found physically obstructed (on the map, but unusable)
        self.map = _WithoutRefuges(sc, self.unknown) if self.unknown else sc
        self.goal_ref = refuge_by_id(sc, cfg.goal_refuge) if cfg.goal_refuge else None
        self.v_max = cfg.v_max or sc.robot.v_max
        self.v_rev = cfg.v_rev_max or sc.robot.v_rev_max
        self.r = sc.robot.radius
        self.comms = policy["name"] not in ("reactive", "backoff") and policy.get("comms", True)
        self.initial_mode = "CRUISE"
        self.mode = "WAIT_START" if cfg.start_delay > 0 else "CRUISE"
        self.phase = ""
        self.entered_t: float | None = None
        self.peers: dict[str, dict] = {}
        self.neg: dict | None = None
        self.ylds: dict | None = None
        if cfg.start_refuge:  # e.g. waiting in the stem of a T-junction: leave like a parked yielder
            ref = refuge_by_id(sc, cfg.start_refuge)
            self.initial_mode, self.phase = "YIELD", "parked"
            self.ylds = {"refuge": ref, "refuge_id": ref.id, "peer": None, "t0": 0.0, "rule": "start",
                         "park_timeout": 0.0, "t_parked": 0.0, "forward_out": True}
            if cfg.start_delay <= 0:
                self.mode = "YIELD"
        self.prc: dict | None = None
        self.fallback_reactive = policy["name"] in ("reactive", "backoff")
        self.n_backoff = 0  # `backoff`: reactive yields so far; the patience window doubles after each
        self.blocked: dict | None = None
        self.no_neg_until: dict[str, float] = {}
        self.reactive_until: float | None = None
        self.last_state_t = -1e9
        self.events: list[dict] = []
        self.decisions: list[dict] = []
        self.msgs_sent = 0
        self.n_yields = 0
        self.done_t: float | None = None

    # ------------------------------------------------------------------ helpers
    def log(self, t, kind, **kw):
        self.events.append({"t": round(t, 3), "agent": self.id, "event": kind, **kw})

    def facing(self) -> float:
        return 0.0 if self.dir > 0 else math.pi

    def snapshot(self, t, pose) -> Snapshot:
        x, _, th, v = pose
        fwd = v * math.cos(th - self.facing())
        group = self.followers(t, x) if self.policy.get("name") == "group_bid" else None
        return Snapshot(self.id, t, x, self.dir, max(0.0, fwd), self.goal_x, self.entered_t,
                        self.cfg.urgency, self.cfg.loaded, self.v_max, self.v_rev,
                        self.sc.robot.w_max, self.sc.robot.a_max, group=group or None)

    def followers(self, t, x) -> list[Snapshot]:
        """Same-direction robots behind us (from STATE) that will also meet the oncoming robot."""
        out = []
        for pid in sorted(self.peers):
            s = self.fresh_peer(pid, t)
            if (s is None or s["dir"] != self.dir or s["mode"] in ("DONE", "YIELD")
                    or not 0 < self.dir * (x - s["x"]) < self.p.detect_range):
                continue
            out.append(Snapshot(pid, t, s["x"], s["dir"], max(0.0, s["v"]), s["goal_x"], s.get("entered_t"),
                                s.get("urgency", 1.0), s.get("loaded", False), self.v_max, self.v_rev,
                                self.sc.robot.w_max, self.sc.robot.a_max))
        return sorted(out, key=lambda f: -self.dir * f.x)

    def fresh_peer(self, pid: str, t: float) -> dict | None:
        s = self.peers.get(pid)
        if s is None or t - s["_rx"] > self.p.state_timeout:
            return None
        return s

    def gap(self, pose, points: np.ndarray, sign: int) -> float:
        """Free distance along the robot's x-axis (sign +1 forward, -1 reverse) to the nearest obstacle point."""
        if len(points) == 0:
            return float("inf")
        x, y, th, _ = pose
        dx, dy = points[:, 0] - x, points[:, 1] - y
        px = math.cos(th) * dx + math.sin(th) * dy
        py = -math.sin(th) * dx + math.cos(th) * dy
        m = (np.abs(py) < self.r + self.p.lateral_margin) & (sign * px > 0)
        if not m.any():
            return float("inf")
        return float(np.min(sign * px[m])) - self.r

    def safe_v(self, pose, points, v: float) -> float:
        if abs(v) < 1e-6:
            return 0.0
        g = self.gap(pose, points, 1 if v > 0 else -1) - self.p.stop_margin
        cap = math.sqrt(2 * self.sc.robot.a_max * max(0.0, g))
        return math.copysign(min(abs(v), cap), v)

    # ------------------------------------------------------------------ low-level controllers
    def lane_cmd(self, pose, target_x: float, v_cap: float | None = None):
        """Follow the centreline y=0 to target_x keeping the robot facing its travel direction."""
        x, y, th, _ = pose
        d = target_x - x
        if abs(d) < self.p.goal_tol:
            return 0.0, self.p.k_heading * wrap(self.facing() - th), True
        s = 1 if d > 0 else -1
        forward = s == self.dir
        look = (s * self.p.lane_lookahead, -y)
        motion_heading = math.atan2(look[1], look[0])
        tgt = motion_heading if forward else wrap(motion_heading + math.pi)
        err = wrap(tgt - th)
        vlim = self.v_max if forward else self.v_rev
        if v_cap is not None:
            vlim = min(vlim, v_cap)
        speed = min(vlim, self.p.k_dist * abs(d), math.sqrt(2 * self.sc.robot.a_max * abs(d)))
        speed *= max(0.0, math.cos(err)) if abs(err) < 0.6 else 0.0
        return (speed if forward else -speed), self.p.k_heading * err, False

    def point_cmd(self, pose, tx: float, ty: float, reverse: bool):
        x, y, th, _ = pose
        dx, dy = tx - x, ty - y
        dist = math.hypot(dx, dy)
        if dist < 0.03:
            return 0.0, 0.0, True
        tgt = math.atan2(dy, dx)
        if reverse:
            tgt = wrap(tgt + math.pi)
        err = wrap(tgt - th)
        vlim = self.v_rev if reverse else self.v_max
        speed = min(vlim, self.p.k_dist * dist, math.sqrt(2 * self.sc.robot.a_max * dist))
        speed *= max(0.0, math.cos(err)) if abs(err) < 0.6 else 0.0
        if dist < 0.08:
            err = 0.0
        return (-speed if reverse else speed), self.p.k_heading * err, False

    def rotate_cmd(self, pose, th_target: float):
        err = wrap(th_target - pose[2])
        if abs(err) < 0.03:
            return 0.0, 0.0, True
        w = max(-0.8 * self.sc.robot.w_max, min(0.8 * self.sc.robot.w_max, 3.0 * err))
        return 0.0, w, False

    # ------------------------------------------------------------------ messaging
    def state_msg(self, t, pose) -> dict:
        x, y, th, v = pose
        return {"type": "STATE", "sender": self.id, "t": t, "x": x, "y": y, "theta": th, "v": v,
                "dir": self.dir, "goal_x": self.goal_x, "mode": self.mode, "phase": self.phase,
                "refuge": (self.ylds or {}).get("refuge_id"), "entered_t": self.entered_t,
                "with": (self.ylds or self.prc or {}).get("peer"),
                "goal_ref": self.goal_ref.id if self.goal_ref is not None else None,
                "urgency": self.cfg.urgency, "loaded": self.cfg.loaded}

    def bid_msg(self, t) -> dict:
        n = self.neg
        return {"type": "BID", "sender": self.id, "to": n["peer"], "t": t, "conflict": n["cid"],
                "snapshot": n["mine"].to_dict(), "have_peer": n["theirs"] is not None,
                "decision": {"yielder": n["dec"].yielder, "refuge": n["dec"].refuge} if n.get("dec") and t >= n.get("ready", t) else None,
                "have_dec": n.get("their_dec") is not None,
                "known": self.known_bays() if self.may_share(n["peer"]) else None,
                "blocked": sorted(self.obstructed) or None}

    def known_bays(self) -> list[str]:
        return sorted(r.id for r in self.map.refuges() if r.kind == "bay")

    def may_share(self, pid) -> bool:
        return self.p.share_map and (not self.p.share_on_detect or pid in self.detected)

    def sense(self, t, pose, perc: Perception, out: list):
        """Explore mode: add bays that come within lidar range of the corridor lane. Mark peers our sensor has seen
        (a sensed object at a peer's STATE position); with share_on_detect, send that peer our map once."""
        x, y = pose[0], pose[1]
        rng = self.sc.robot.lidar_range
        if self.p.explore and self.unknown and abs(y) <= self.sc.half_width:
            seen = [r.id for r in self.sc.refuges() if r.id in self.unknown and abs(r.x - x) <= rng]
            if seen:
                self.learn_refuges(t, seen, "sensed")
        for pid in sorted(self.peers):
            s = self.fresh_peer(pid, t)
            if pid in self.detected or s is None or math.hypot(s["x"] - x, s["y"] - y) > rng:
                continue
            if any(math.hypot(px - s["x"], py - s["y"]) < 2 * self.r for px, py in perc.peers):
                self.detected.add(pid)
                self.log(t, "peer_detected", peer=pid)
                if self.comms and self.p.share_map and self.p.share_on_detect:
                    out.append({"type": "MAP", "sender": self.id, "to": pid, "t": t, "known": self.known_bays(),
                                "blocked": sorted(self.obstructed) or None})

    def learn_refuges(self, t, ids, source):
        for rid in ids:
            if rid in self.unknown:
                self.unknown.discard(rid)
                self.log(t, "refuge_learned", refuge=rid, source=source)
        self.rebuild_map()

    def rebuild_map(self):
        hide = self.unknown | self.obstructed
        self.map = _WithoutRefuges(self.sc, hide) if hide else self.sc

    def learn_obstructed(self, t, ids, source):
        new = set(ids) - self.obstructed
        if new:
            self.obstructed |= new
            self.log(t, "obstructed_learned", refuges=sorted(new), source=source)
            self.rebuild_map()

    def handle(self, t, pose, msg):
        if msg["type"] == "STATE":
            self.peers[msg["sender"]] = {**msg, "_rx": t}
        elif msg["type"] == "MAP" and msg.get("to") == self.id:
            self.map_from.add(msg["sender"])
            self.learn_refuges(t, msg.get("known") or [], msg["sender"])
            if msg.get("blocked"):
                self.learn_obstructed(t, msg["blocked"], msg["sender"])
        elif msg["type"] == "BID" and msg["to"] == self.id:
            pid = msg["sender"]
            if msg.get("known") is not None:  # BIDs repeat the map once the sender may share it (lossy links)
                self.map_from.add(pid)
            if msg.get("known"):
                self.learn_refuges(t, msg["known"], pid)
            if msg.get("blocked"):
                self.learn_obstructed(t, msg["blocked"], pid)
            if self.neg is None or self.neg["peer"] != pid:
                if self.comms and (self.mode in ("CRUISE", "NEGOTIATE") or self.can_renegotiate(pid)):
                    self.start_neg(t, pose, pid, cid=msg["conflict"])
                else:
                    return
            n = self.neg
            if n["theirs"] is None or (n.get("dec") is None and self.holds()):
                n["theirs"] = Snapshot.from_dict(msg["snapshot"])
            if msg["have_peer"]:
                n["acked"] = True
            if msg.get("decision"):
                n["their_dec"] = msg["decision"]
            if msg.get("have_dec"):
                n["dec_acked"] = True

    def holds(self) -> bool:
        return self.p.hold_for_map and self.p.share_map and self.p.share_on_detect

    def holding(self, t, n) -> bool:
        """hold_for_map: postpone the decision until we have sensed the peer and received its map."""
        if not self.holds() or (n["peer"] in self.detected and n["peer"] in self.map_from):
            return False
        if t - n["t0"] < self.p.hold_timeout:
            return True
        if not n.get("hold_timeout"):
            n["hold_timeout"] = True
            self.log(t, "hold_timeout", peer=n["peer"])
        return False

    def can_renegotiate(self, pid) -> bool:
        """A proceeding robot that has been released past its yielder may negotiate with a new oncoming robot."""
        c = self.prc
        return self.mode == "PROCEED" and c is not None and c.get("released") and pid != c["peer"]

    def oncoming_conflict(self, t, x, modes, exclude=None):
        for pid, s in list(self.peers.items()):
            s = self.fresh_peer(pid, t)
            if s is None or pid == exclude or t < self.no_neg_until.get(pid, -1):
                continue
            if self.policy["name"] == "reservation" and not (self.sc.in_corridor(x) and self.sc.in_corridor(s["x"])):
                continue  # whoever is inside holds the corridor; negotiate only if both got in
            if (s["dir"] == -self.dir and s["mode"] in modes
                    and self.dir * (s["x"] - x) > 0 and abs(s["x"] - x) < self.p.detect_range):
                return pid
        return None

    def corridor_holder(self, t, x):
        """Reservation policy: an oncoming peer that is inside the corridor while this robot is still outside."""
        entry = 0.0 if self.dir > 0 else self.sc.length
        if self.dir * (entry - x) <= 0:  # already in the corridor or past it
            return None
        for pid in sorted(self.peers):
            s = self.fresh_peer(pid, t)
            if s is not None and s["dir"] == -self.dir and s["mode"] != "DONE" and self.sc.in_corridor(s["x"]):
                return pid
        return None

    def start_neg(self, t, pose, pid, cid=None):
        cid = cid or f"{min(self.id, pid)}-{max(self.id, pid)}@{t:.2f}"
        self.neg = {"peer": pid, "cid": cid, "mine": self.snapshot(t, pose), "theirs": None,
                    "t0": t, "last_tx": -1e9, "acked": False, "decided": None}
        self.mode, self.phase = "NEGOTIATE", ""
        self.log(t, "conflict_detected", peer=pid)

    # ------------------------------------------------------------------ main tick
    def step(self, t: float, pose, perception: Perception, inbox: list[dict]):
        out: list[dict] = []
        for m in inbox:
            self.handle(t, pose, m)
        self.sense(t, pose, perception, out)
        x = pose[0]
        if self.entered_t is None and self.sc.in_corridor(x):
            self.entered_t = t
        v, w = self.tick(t, pose, perception)
        if self.comms:
            if t - self.last_state_t >= 1.0 / self.sc.comms.get("rate", 5.0) - 1e-9:
                out.append(self.state_msg(t, pose))
                self.last_state_t = t
            n = self.neg
            due = n is not None and t - n["last_tx"] >= self.p.neg_period - 1e-9
            if due and (self.mode == "NEGOTIATE" or (n["decided"] is not None and not n.get("dec_acked")
                                                     and t - n["decided"] < self.p.neg_timeout)):
                out.append(self.bid_msg(t))
                n["last_tx"] = t
        self.msgs_sent += len(out)
        return v, w, out

    def tick(self, t, pose, perc: Perception):
        m = self.mode
        if m == "WAIT_START":
            if t >= self.cfg.start_delay:
                self.mode = self.initial_mode
            return 0.0, 0.0
        if m == "DONE":
            return 0.0, 0.0
        if m == "NEGOTIATE":
            return self.tick_negotiate(t, pose, perc)
        if m == "YIELD":
            return self.tick_yield(t, pose, perc)
        if m == "PROCEED":
            return self.tick_proceed(t, pose, perc)
        return self.tick_cruise(t, pose, perc)

    def yielding_peer(self, t, x):
        """A fresh, oncoming peer that has announced it is yielding (so this robot should proceed)."""
        for pid, s in list(self.peers.items()):
            s = self.fresh_peer(pid, t)
            if (s is not None and s["mode"] == "YIELD" and s.get("refuge") and s["dir"] == -self.dir
                    and self.dir * (s["x"] - x) > -0.3):
                return pid, s
        return None

    def make_room(self, t, x, perc):
        """A same-direction robot just ahead must reverse into a refuge we are blocking (e.g. a convoy leader
        that yielded): back into a free refuge of our own. Returns (refuge, proceeder id) or None."""
        for pid in sorted(self.peers):
            s = self.fresh_peer(pid, t)
            if s is None or s["dir"] != self.dir or s["mode"] != "YIELD" or not s.get("refuge"):
                continue
            r = refuge_by_id(self.sc, s["refuge"])
            ahead = self.dir * (s["x"] - x)
            if (r is None or not 0 < ahead < self.p.detect_range or self.dir * (s["x"] - r.x) <= 0
                    or self.dir * (r.x - x) > r.span / 2 + 2 * self.r + 2 * self.sc.clearance):
                continue
            own = [q for q in self.map.refuges() if q.id != r.id and self.dir * (x - q.x) > 0
                   and not self.refuge_taken(t, q, perc)]
            if own:
                return min(own, key=lambda q: abs(q.x - x)), s.get("with") or pid
        return None

    def tick_cruise(self, t, pose, perc):
        x = pose[0]
        if self.goal_ref is None and self.dir * (x - self.goal_x) >= -self.p.goal_tol:
            self.mode, self.done_t = "DONE", t
            self.log(t, "goal_reached")
            return 0.0, 0.0
        mr = self.make_room(t, x, perc) if self.comms else None
        if mr is not None:
            ref, peer = mr
            self.log(t, "make_room", refuge=ref.id, peer=peer)
            self.begin_yield(t, ref, peer, rule="make_room")
            return self.brake()
        yp = self.yielding_peer(t, x) if self.comms else None
        if yp is not None and self.goal_ref is not None:
            yr = refuge_by_id(self.sc, yp[1].get("refuge"))
            if yr is None or yr.id == self.goal_ref.id or self.dir * (yr.x - self.goal_ref.x) > 0:
                yp = None  # we turn off into our destination before reaching the yielder's refuge
        if yp is not None:
            ref = refuge_by_id(self.sc, yp[1]["refuge"])
            if ref is not None and self.dir * (pass_x(ref, self.dir, self.sc) - x) > 0:
                self.log(t, "peer_yielding", peer=yp[0], refuge=ref.id)
                self.begin_proceed(t, ref, yp[0])
                return self.brake()
        if self.fallback_reactive and self.reactive_until is not None and t > self.reactive_until:
            self.fallback_reactive, self.reactive_until = False, None
        if self.policy["name"] == "reservation" and self.comms and not self.fallback_reactive:
            holder = self.corridor_holder(t, x)
            if holder is not None:
                room = next((r for r in self.map.refuges() if r.kind == "room" and (r.x < 0) == (self.dir > 0)), None)
                if room is None or self.refuge_taken(t, room, perc):
                    return self.brake()
                self.begin_yield(t, room, holder, rule="reservation")
                return self.brake()
        if self.comms and not self.fallback_reactive:
            pid = self.oncoming_conflict(t, x, ("CRUISE", "NEGOTIATE", "WAIT_START"))
            if pid is not None:
                self.start_neg(t, pose, pid)
                return self.brake()
        target = self.goal_x
        g = self.goal_ref
        if g is not None:
            if self.refuge_taken(t, g, perc):
                occ = self.goal_occupant(t, g, x)
                if occ is not None:
                    # the occupant will leave towards us: wait in another bay so it can pass
                    w_ref = self.goal_wait_refuge(t, x, g, perc)
                    if w_ref is not None:
                        self.log(t, "goal_wait", peer=occ, refuge=w_ref.id, goal=g.id)
                        self.begin_yield(t, w_ref, occ, rule="goal_wait")
                        return self.brake()
                # destination branch still occupied: wait outside the window its occupant needs to leave
                lim = g.span / 2 + 2 * self.r + 2 * self.sc.clearance + 2.0 + 0.3
                target = g.x - self.dir * lim
                if self.dir * (target - x) < -0.1:
                    # inside the occupant's exit window: back off to the wait point if the lane behind is clear
                    behind = any(
                        0 < self.dir * (x - px) < 1.0 and abs(py) < self.sc.half_width + 0.1
                        for px, py in perc.peers
                    )
                    if behind:
                        return self.brake()
                    v, w, _ = self.point_cmd(pose, target, 0.0, reverse=True)
                    return v, w
                if self.dir * (target - x) <= 0:
                    return self.brake()
            elif self.dir * (x - g.x) >= -self.p.goal_tol:
                self.begin_yield(t, g, None, rule="goal")
                self.n_yields -= 1
                self.ylds["goal"] = True
                self.phase = "turn_in"
                return self.brake()
        v, w, _ = self.lane_cmd(pose, target)
        vs = self.safe_v(pose, perc.points, v)
        if self.fallback_reactive and self.reactive_blocked(t, pose, perc, v, vs):
            return self.brake()
        return vs, w

    def goal_occupant(self, t, g: Refuge, x: float):
        """Peer we should let pass while our destination is occupied: its occupant leaving towards us,
        or an oncoming robot in the corridor (waiting in the lane would block it)."""
        if not self.comms:
            return None
        for pid in list(self.peers):
            s = self.fresh_peer(pid, t)
            if s is None or s["dir"] != -self.dir or s.get("goal_ref") == g.id:
                continue
            if s.get("refuge") == g.id:
                return pid
            if s["mode"] in ("CRUISE", "NEGOTIATE") and 0 < self.dir * (s["x"] - x) < self.p.detect_range:
                return pid
        return None

    def goal_wait_refuge(self, t, x, g: Refuge, perc):
        """Closest free bay before our destination (ahead preferred) to wait in while its occupant leaves."""
        cands = [r for r in self.map.refuges()
                 if r.kind == "bay" and r.id != g.id and self.dir * (g.x - r.x) > g.span / 2 + r.span / 2
                 and not self.refuge_taken(t, r, perc)]
        ahead = [r for r in cands if self.dir * (r.x - x) >= -0.05]
        pool = ahead or [r for r in cands if self.dir * (x - r.x) < 3.0]
        return min(pool, key=lambda r: abs(r.x - x)) if pool else None

    def brake(self):
        return 0.0, 0.0

    # ------------------------------------------------------------------ reactive (no comms) behaviour
    def reactive_blocked(self, t, pose, perc, v, vs) -> bool:
        """Start a yield manoeuvre if blocked by an oncoming robot for longer than `patience`."""
        if abs(v) < 0.05 or abs(vs) > 0.03 or not perc.peers:
            self.blocked = None
            return False
        g = self.gap(pose, perc.points, 1)
        if self.blocked is None:
            if self.policy["name"] == "backoff":  # randomized exponential backoff: U[0, base * 2^k]
                hi = self.policy.get("base", self.p.patience[1]) * 2 ** min(self.n_backoff, 5)
                pat = float(self.rng.uniform(0.0, hi))
            else:
                pat = float(self.rng.uniform(*self.p.patience))
            self.blocked = {"t0": t, "gap": g, "patience": pat}
            return False
        if g > self.blocked["gap"] + 0.05:
            self.blocked = None
            return False
        if t - self.blocked["t0"] < self.blocked["patience"]:
            return False
        x = pose[0]
        behind = [r for r in self.map.refuges()
                  if self.dir * (r.x - x) <= 0.05 and self.dir * (self.goal_x - r.x) > 0
                  and not self.refuge_taken(t, r, perc)]
        if not behind:
            return False
        ref = min(behind, key=lambda r: abs(r.x - x))
        self.blocked = None
        self.n_backoff += 1
        self.begin_yield(t, ref, peer=None, rule="reactive")
        return True

    # ------------------------------------------------------------------ negotiation
    def tick_negotiate(self, t, pose, perc):
        n = self.neg
        if n["theirs"] is None:
            yp = self.yielding_peer(t, pose[0])
            if yp is not None and yp[0] == n["peer"]:
                self.neg, self.mode = None, "CRUISE"
                return self.tick_cruise(t, pose, perc)
            if t - n["t0"] > self.p.neg_timeout:
                self.log(t, "negotiation_timeout", peer=n["peer"])
                self.no_neg_until[n["peer"]] = t + 10.0
                self.neg, self.mode = None, "CRUISE"
                self.fallback_reactive = True
            return self.brake()
        if n.get("dec") is None and self.holding(t, n):
            n["mine"] = self.snapshot(t, pose)
            v, w, _ = self.lane_cmd(pose, self.goal_x)
            return self.safe_v(pose, perc.points, v), w
        if n.get("dec") is None:
            taken = {r.id for r in self.map.refuges()
                     if r.kind == "bay" and self.refuge_taken(t, r, perc, ignore=n["peer"])}
            sc = _WithoutRefuges(self.map, taken) if taken else self.map
            d: Decision = decide(self.policy, [n["mine"], n["theirs"]], sc)
            think = float(d.detail.get("think_time", 0.0))  # deliberation time (LLM latency), charged in sim time
            n["decided"], n["dec"], n["ready"] = t + think, d, t + think
            rec = {"t": t, "agent": self.id, "peer": n["peer"], "yielder": d.yielder, "refuge": d.refuge,
                   "rule": d.rule, "t_detect": n["t0"], **{k: v for k, v in d.detail.items() if k != "plan"}}
            if "plan" in d.detail:
                rec["predicted"] = d.detail["plan"]
            self.decisions.append(rec)
            self.log(t, "decision", yielder=d.yielder, refuge=d.refuge, rule=d.rule)
        if t < n.get("ready", t):
            return self.brake()
        d = n["dec"]
        td = n.get("their_dec")
        # commit: act once the peer's decision has arrived (or the commit window expires)
        if self.p.commit and td is None and t - n["decided"] < self.p.neg_timeout:
            return self.brake()
        yielder, ref = d.yielder, refuge_of(d, self.sc)
        if td is not None and (td["yielder"], td["refuge"]) != (d.yielder, d.refuge):
            if self.id > n["peer"]:  # disagreement after lost messages: the lower id's decision wins
                yielder = td["yielder"]
                ref = refuge_by_id(self.sc, td["refuge"]) if td["refuge"] else None
                if ref is not None:  # the peer's decision may name a bay we didn't know
                    self.learn_refuges(t, [ref.id], n["peer"])
            self.log(t, "decision_mismatch", adopted=self.id > n["peer"], yielder=yielder)
        elif td is None:
            self.log(t, "commit_timeout", peer=n["peer"])
        if ref is None:
            # no usable refuge right now (e.g. all taken): act reactively, renegotiate once one may be free
            self.mode, self.fallback_reactive = "CRUISE", True
            self.no_neg_until[n["peer"]] = self.reactive_until = t + 10.0
        elif yielder == self.id:
            self.begin_yield(t, ref, peer=n["peer"], rule=d.rule)
        else:
            self.begin_proceed(t, ref, n["peer"])
        return self.brake()

    def begin_yield(self, t, ref: Refuge, peer, rule):
        self.mode, self.phase = "YIELD", "to_refuge"
        self.n_yields += 1
        self.ylds = {"refuge": ref, "refuge_id": ref.id, "peer": peer, "t0": t, "rule": rule,
                     "park_timeout": float(self.rng.uniform(*self.p.park_timeout))}
        self.log(t, "yield_start", refuge=ref.id, rule=rule)

    def begin_proceed(self, t, ref: Refuge, peer):
        self.mode, self.phase = "PROCEED", "hold"
        self.prc = {"refuge": ref, "peer": peer, "t0": t, "hold": hold_x(ref, self.dir, self.sc),
                    "pass": pass_x(ref, self.dir, self.sc)}
        self.log(t, "proceed_start", refuge=ref.id)

    def peer_out_of_lane(self, t, peer, ref: Refuge, perc) -> bool:
        s = self.fresh_peer(peer, t) if peer else None
        if s is not None:
            if s["mode"] == "YIELD" and s["phase"] == "parked":
                return True
            if s["mode"] == "DONE":
                return True
        hw = self.sc.half_width
        near = [(px, py) for px, py in perc.peers if abs(px - ref.x) < ref.span / 2 + 0.3]
        return any(abs(py) > hw + 0.15 for _, py in near) and not any(abs(py) < hw for _, py in near)

    def tick_proceed(self, t, pose, perc):
        c = self.prc
        x = pose[0]
        if c.get("released"):
            pid = self.oncoming_conflict(t, x, ("CRUISE", "NEGOTIATE"), exclude=c["peer"]) if self.comms else None
            if pid is not None:
                self.prc = None
                self.start_neg(t, pose, pid)
                return self.brake()
            if self.dir * (x - c["pass"]) > 0 or self.dir * (x - self.goal_x) >= -self.p.goal_tol:
                self.mode, self.phase, self.prc, self.neg = "CRUISE", "", None, None
                self.log(t, "passed_refuge")
            v, w, _ = self.lane_cmd(pose, self.goal_x)
            return self.safe_v(pose, perc.points, v), w
        s = self.fresh_peer(c["peer"], t) if self.comms else None
        if s is not None and s["mode"] == "CRUISE" and s["dir"] != self.dir and self.dir * (s["x"] - x) > 0:
            # the robot we are waiting for is driving towards us, not yielding: the agreement is stale
            self.log(t, "proceed_contradicted", peer=c["peer"])
            self.prc = None
            self.start_neg(t, pose, s["sender"])
            return self.brake()
        if self.peer_out_of_lane(t, c["peer"], c["refuge"], perc):
            c["released"] = True
            self.phase = "pass"
            self.log(t, "released")
        elif t - c["t0"] > self.p.proceed_timeout:
            self.log(t, "proceed_timeout")
            self.mode, self.prc, self.neg, self.fallback_reactive = "CRUISE", None, None, True
            return self.brake()
        target = c["hold"] if self.dir * (c["hold"] - x) > 0 else x
        v, w, _ = self.lane_cmd(pose, target)
        return self.safe_v(pose, perc.points, v), w

    def peer_passed(self, t, pose, perc) -> bool:
        c = self.ylds
        ref: Refuge = c["refuge"]
        need = ref.span / 2 + self.r + self.sc.clearance
        pdir = -self.dir
        for pid in list(self.peers):  # e.g. a convoy follower that is also passing this refuge
            s = self.fresh_peer(pid, t)
            if (pid != c["peer"] and s is not None and s["mode"] == "PROCEED" and s.get("with") == self.id
                    and pdir * (s["x"] - ref.x) <= need):
                return False
        if c["peer"]:
            s = self.fresh_peer(c["peer"], t)
            if s is not None:
                return s["mode"] == "DONE" or pdir * (s["x"] - ref.x) > need
        if any(pdir * (px - ref.x) > need and abs(py) < self.sc.half_width + 0.1 for px, py in perc.peers):
            return self.lane_clear(ref, perc)
        if t - c["t_parked"] > c["park_timeout"]:
            return self.lane_clear(ref, perc)
        return False

    def lane_clear(self, ref: Refuge, perc, extra: float = 0.0, t: float | None = None) -> bool:
        base = ref.span / 2 + 2 * self.r + 2 * self.sc.clearance
        waiting = [] if t is None else [
            s["x"] for pid in list(self.peers)
            if (s := self.fresh_peer(pid, t)) is not None and s.get("goal_ref") == ref.id and abs(s["v"]) < 0.05
        ]
        return not any(
            abs(px - ref.x) < base + extra
            and abs(py) < self.sc.half_width + 0.1
            # a stationary robot waiting to enter this refuge only blocks us inside the base window
            and not (abs(px - ref.x) >= base and any(abs(px - wx) < 0.3 for wx in waiting))
            for px, py in self.known_peer_positions(t, perc, ref)
        )

    def known_peer_positions(self, t, perc, ref: Refuge | None = None) -> list:
        """Sensed peers plus peers whose fresh STATE says they are driving towards `ref`
        (a real lidar inside a deep refuge is occluded by its walls)."""
        pts = list(perc.peers)
        if t is not None and ref is not None:
            pts += [(s["x"], s["y"]) for pid in list(self.peers)
                    if (s := self.fresh_peer(pid, t)) is not None and s["mode"] != "DONE"
                    and abs(s["v"]) > 0.05 and s["dir"] * (ref.x - s["x"]) > 0]
        return pts

    def refuge_taken(self, t, ref: Refuge, perc, ignore=None) -> bool:
        for pid in list(self.peers):
            if pid == ignore:
                continue
            s = self.fresh_peer(pid, t)
            if self.p.state_guard and s is not None and s["mode"] == "YIELD" and s.get("refuge") == ref.id:
                return True
        return self.p.bay_check and self.bay_seen_occupied(ref, perc)

    def robot_in_refuge(self, t, ref: Refuge) -> bool:
        """A known peer (from STATE) is physically in this refuge; otherwise an occupied bay is an obstruction."""
        for pid in list(self.peers):
            s = self.fresh_peer(pid, t)
            if s is not None and abs(s["x"] - ref.x) < ref.span / 2 + 0.3 and abs(s["y"]) > self.sc.half_width - 0.1:
                return True
        return False

    def fallback_refuge(self, t, x, bad: Refuge, perc):
        """Nearest usable refuge behind us (the way we can reverse without meeting the proceeder)."""
        cands = [r for r in self.map.refuges() if r.id != bad.id and r.id not in self.obstructed
                 and self.dir * (x - r.x) > 0 and not self.refuge_taken(t, r, perc)]
        return min(cands, key=lambda r: abs(r.x - x)) if cands else None

    def bay_seen_occupied(self, ref: Refuge, perc) -> bool:
        hw = self.sc.half_width
        return any(abs(px - ref.x) < ref.span / 2 + 0.1 and abs(py) > hw - 0.05 and py * ref.side > 0
                   for px, py in perc.peers) if ref.kind == "bay" else False

    def passer_pending(self, t, ref: Refuge) -> bool:
        """A peer is still proceeding past this refuge on the understanding that we wait in it."""
        need = ref.span / 2 + 2 * self.r
        for pid in list(self.peers):
            s = self.fresh_peer(pid, t)
            if s is not None and s["mode"] == "PROCEED" and s.get("with") == self.id \
                    and s["dir"] * (s["x"] - ref.x) <= need:
                return True
        return False

    def tick_yield(self, t, pose, perc):
        c = self.ylds
        ref: Refuge = c["refuge"]
        ph = self.phase
        if self.p.state_guard and ph in ("to_refuge", "turn_in") and not c.get("goal"):
            # two robots heading for the same refuge (e.g. after lost bids): the higher id gives way
            for pid in list(self.peers):
                s = self.fresh_peer(pid, t)
                if (s is not None and s["mode"] == "YIELD" and s.get("refuge") == ref.id
                        and s["phase"] in ("to_refuge", "turn_in", "park_in", "parked")
                        and (s["phase"] != ph or self.id > pid)
                        and self.dir * (pass_x(ref, self.dir, self.sc) - pose[0]) > 0):
                    self.log(t, "yield_conflict", peer=pid, refuge=ref.id)
                    self.n_yields -= 1
                    self.ylds = None
                    self.begin_proceed(t, ref, pid)
                    return self.brake()
        if self.p.state_guard and ph == "to_refuge" and c["peer"] is not None and self.id > c["peer"]:
            # lost messages left both robots yielding to each other in different refuges: the lower id keeps yielding
            s = self.fresh_peer(c["peer"], t)
            if (s is not None and s["mode"] == "YIELD" and s.get("with") == self.id and s.get("refuge")
                    and s["phase"] in ("to_refuge", "turn_in", "park_in", "parked")):
                pref = refuge_by_id(self.sc, s["refuge"])
                self.log(t, "yield_conflict", peer=c["peer"], refuge=pref.id)
                self.n_yields -= 1
                self.ylds = None
                self.begin_proceed(t, pref, c["peer"])
                return self.brake()
        if ph == "to_refuge":
            v, w, done = self.lane_cmd(pose, ref.x)
            if done and self.bay_seen_occupied(ref, perc) and not self.robot_in_refuge(t, ref):
                # the bay is obstructed by something that is not a robot (our map is wrong): keep yielding elsewhere
                alt = self.fallback_refuge(t, pose[0], ref, perc)
                if alt is not None:
                    self.log(t, "refuge_blocked", refuge=ref.id, alt=alt.id)
                    self.obstructed.add(ref.id)
                    self.rebuild_map()
                    self.n_yields -= 1
                    self.begin_yield(t, alt, c["peer"], rule="refuge_blocked")
                    return self.brake()
            if done and self.p.bay_check and self.bay_seen_occupied(ref, perc):
                # sensors show another robot already in the bay (decisions diverged): pass it instead
                self.log(t, "refuge_occupied", refuge=ref.id)
                self.n_yields -= 1
                pid = c["peer"]
                self.ylds = None
                self.begin_proceed(t, ref, pid)
                return self.brake()
            if done:
                self.phase = "turn_in"
            return self.safe_v(pose, perc.points, v), w
        if ph == "turn_in":
            v, w, done = self.rotate_cmd(pose, ref.side * math.pi / 2)
            if done:
                self.phase = "park_in"
            return v, w
        if ph == "park_in":
            v, w, done = self.point_cmd(pose, ref.x, ref.park_y, reverse=False)
            if done and c.get("goal"):
                self.mode, self.done_t, self.phase = "DONE", t, ""
                self.log(t, "goal_reached", refuge=ref.id)
            elif done:
                self.phase, c["t_parked"] = "parked", t
                self.log(t, "parked", refuge=ref.id)
            return v, w
        if ph == "parked":
            if self.peer_passed(t, pose, perc):
                self.phase = "back_out"
                self.log(t, "leaving_refuge", refuge=ref.id)
            return 0.0, 0.0
        if ph == "back_out":
            if not self.lane_clear(ref, perc, extra=2.0 if c.get("forward_out") else 0.0, t=t) or self.passer_pending(t, ref):
                if abs(pose[1]) > self.sc.half_width + self.r:
                    self.phase = "parked"  # still inside the refuge: let the peer pass first
                    return 0.0, 0.0
                if not c.get("forward_out"):
                    self.phase = "park_in"  # partly out and the lane is not clear: drive back in and wait
                    return 0.0, 0.0
                # leaving a T-junction stem and already in the lane: join it and negotiate normally
            v, w, done = self.point_cmd(pose, ref.x, 0.0, reverse=not c.get("forward_out"))
            if done:
                self.phase = "turn_out"
            return v, w
        if ph == "turn_out":
            v, w, done = self.rotate_cmd(pose, self.facing())
            if done:
                self.log(t, "yield_done", refuge=ref.id)
                self.mode, self.phase, self.ylds, self.neg = "CRUISE", "", None, None
            return v, w
        raise RuntimeError(ph)


class _WithoutRefuges:
    """Scenario view that hides refuges already occupied by a third robot."""

    def __init__(self, sc: Scenario, taken: set[str]):
        self._sc, self._taken = sc, taken

    def __getattr__(self, name):
        return getattr(self._sc, name)

    def refuges(self):
        return [r for r in self._sc.refuges() if r.id not in self._taken]


def is_negotiating(policy: dict) -> bool:
    return policy["name"] in NEGOTIATING_POLICIES
