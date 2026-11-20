"""Scenario geometry: a straight single-lane corridor along +x with pull-in bays and end rooms.

World frame: the corridor centreline is y = 0, running from x = 0 to x = length. Rooms of size
room_length x room_width sit at both ends. Robots start in the rooms and drive through the
corridor to a goal in the opposite room.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class RobotSpec:
    """Kinematic envelope of a TurtleBot3 Waffle (defaults from the ROBOTIS e-manual / model SDF).

    `radius` is the swept radius about the wheel axle (base_footprint): the Waffle's body box is
    0.265 m square centred 0.064 m behind the axle, so rotating in place sweeps ~0.25 m.
    """

    radius: float = 0.25
    # body rectangle in the base_footprint frame (x0, x1, y0, y1): Waffle is 281 x 306 mm
    footprint: tuple = (-0.2045, 0.0765, -0.153, 0.153)
    v_max: float = 0.26
    v_rev_max: float = 0.15
    w_max: float = 1.82
    a_max: float = 0.5
    alpha_max: float = 3.0
    lidar_range: float = 3.5


@dataclass
class Refuge:
    """A place to pull out of the lane: a bay off the corridor, or a parking spot in an end room.

    The yielding robot drives along the lane to `x`, turns to face `side`, and drives to
    `park_y`. `span` is the x-extent the proceeding robot must keep clear of until the
    yielder is parked.
    """

    id: str
    x: float
    side: int
    park_y: float
    span: float
    kind: str = "bay"


@dataclass
class Rect:
    x0: float
    x1: float
    y0: float
    y1: float

    def contains(self, x: float, y: float, eps: float = 1e-6) -> bool:
        return self.x0 - eps <= x <= self.x1 + eps and self.y0 - eps <= y <= self.y1 + eps


@dataclass
class AgentConfig:
    id: str
    start_x: float
    goal_x: float
    start_delay: float = 0.0
    urgency: float = 1.0
    loaded: bool = False
    v_max: float | None = None
    v_rev_max: float | None = None
    start_refuge: str | None = None  # start parked in this refuge, e.g. the stem of a T-junction (a deep bay)
    known_refuges: list[str] | None = None  # bays this robot knows about (None = all); end rooms always known
    goal_refuge: str | None = None

    @property
    def direction(self) -> int:
        return 1 if self.goal_x > self.start_x else -1


@dataclass
class Scenario:
    name: str = "corridor_single_bay"
    length: float = 8.0
    width: float = 0.65
    room_length: float = 2.5
    room_width: float = 2.5
    bays: list[dict] = field(default_factory=lambda: [{"x": 4.0, "side": 1, "width": 0.8, "depth": 0.6}])
    room_refuges: bool = True
    blocked_bays: list[str] = field(default_factory=list)  # bays on every map but physically obstructed (pallet, closed off)
    agent_params: dict = field(default_factory=dict)  # AgentParams defaults for every robot (e.g. explore); a policy's agent_params override them
    despawn_done: bool = False  # robots that reach their goal leave the world (convoys: a parked finisher would block the lane)
    robot: RobotSpec = field(default_factory=RobotSpec)
    agents: list[AgentConfig] = field(default_factory=list)
    clearance: float = 0.05
    dt: float = 0.05
    t_max: float = 180.0
    comms: dict = field(default_factory=lambda: {"latency": 0.05, "jitter": 0.0, "loss": 0.0, "rate": 5.0})

    @property
    def half_width(self) -> float:
        return self.width / 2.0

    def free_rects(self) -> list[Rect]:
        hw, L = self.half_width, self.length
        rects = [
            Rect(0.0, L, -hw, hw),
            Rect(-self.room_length, 0.0, -self.room_width / 2, self.room_width / 2),
            Rect(L, L + self.room_length, -self.room_width / 2, self.room_width / 2),
        ]
        for b in self.bays:
            y0, y1 = (hw, hw + b["depth"]) if b["side"] > 0 else (-hw - b["depth"], -hw)
            rects.append(Rect(b["x"] - b["width"] / 2, b["x"] + b["width"] / 2, y0, y1))
        return rects

    def wall_segments(self) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        """Boundary of the free space as line segments (used for lidar map-filtering and the SDF world)."""
        hw, L, rl, rw = self.half_width, self.length, self.room_length, self.room_width / 2
        segs = []
        for side in (1, -1):
            bays = sorted([b for b in self.bays if b["side"] == side], key=lambda b: b["x"])
            y = side * hw
            x = 0.0
            for b in bays:
                bx0, bx1, yb = b["x"] - b["width"] / 2, b["x"] + b["width"] / 2, side * (hw + b["depth"])
                segs.append(((x, y), (bx0, y)))
                segs += [((bx0, y), (bx0, yb)), ((bx0, yb), (bx1, yb)), ((bx1, yb), (bx1, y))]
                x = bx1
            segs.append(((x, y), (L, y)))
            segs.append(((0.0, side * hw), (0.0, side * rw)))
            segs.append(((L, side * hw), (L, side * rw)))
            segs.append(((-rl, side * rw), (0.0, side * rw)))
            segs.append(((L, side * rw), (L + rl, side * rw)))
        segs.append(((-rl, -rw), (-rl, rw)))
        segs.append(((L + rl, -rw), (L + rl, rw)))
        return segs

    def refuges(self) -> list[Refuge]:
        r, hw, c = self.robot.radius, self.half_width, self.clearance
        out = []
        for i, b in enumerate(self.bays):
            park = hw + b["depth"] - r - c
            out.append(Refuge(f"bay{i}", b["x"], int(b["side"]), b["side"] * park, b["width"], "bay"))
        if self.room_refuges:
            off = r + 2 * c + 0.3
            park = hw + 2 * r + 2 * c
            out.append(Refuge("room_lo", -off, 1, park, 2 * off, "room"))
            out.append(Refuge("room_hi", self.length + off, 1, park, 2 * off, "room"))
        return out

    def start_pose(self, a: AgentConfig) -> tuple[float, float, float]:
        if a.start_refuge:
            r = next(r for r in self.refuges() if r.id == a.start_refuge)
            return r.x, r.park_y, -r.side * math.pi / 2
        return a.start_x, 0.0, 0.0 if a.direction > 0 else math.pi

    def in_corridor(self, x: float) -> bool:
        return 0.0 <= x <= self.length

    def circle_free(self, x: float, y: float, r: float, n: int = 16) -> bool:
        rects = self.free_rects()
        pts = [(x, y)] + [(x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
        return all(any(R.contains(px, py) for R in rects) for px, py in pts)


def _apply(obj, data: dict):
    for k, v in data.items():
        if not hasattr(obj, k):
            raise KeyError(f"unknown scenario key: {k}")
        setattr(obj, k, v)


def scenario_from_dict(data: dict) -> Scenario:
    data = copy.deepcopy(data)
    sc = Scenario()
    robot = data.pop("robot", {})
    agents = data.pop("agents", None)
    comms = data.pop("comms", {})
    _apply(sc, data)
    _apply(sc.robot, robot)
    sc.comms = {**sc.comms, **comms}
    if agents is None:
        agents = [
            {"id": "A", "start_x": -1.0, "goal_x": sc.length + 2.0},
            {"id": "B", "start_x": sc.length + 1.0, "goal_x": -2.0},
        ]
    sc.agents = [AgentConfig(**a) for a in agents]
    return sc


def load_scenario(path: str | Path, overrides: dict | None = None) -> Scenario:
    data = yaml.safe_load(Path(path).read_text()) or {}
    if overrides:
        data = deep_update(data, overrides)
    return scenario_from_dict(data)


def deep_update(base: dict, upd: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_update(out[k], v)
        else:
            out[k] = v
    return out


def footprint_corners(x: float, y: float, th: float, fp) -> list[tuple[float, float]]:
    c, s = math.cos(th), math.sin(th)
    x0, x1, y0, y1 = fp
    return [(x + c * px - s * py, y + s * px + c * py) for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]


def footprints_overlap(p, q, fp) -> bool:
    """Separating-axis test between two robot rectangles; p, q = (x, y, theta)."""
    A, B = footprint_corners(*p[:3], fp), footprint_corners(*q[:3], fp)
    for poly in (A, B):
        for i in range(4):
            (ax, ay), (bx, by) = poly[i], poly[(i + 1) % 4]
            nx, ny = by - ay, ax - bx
            pa = [nx * u + ny * v for u, v in A]
            pb = [nx * u + ny * v for u, v in B]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True
