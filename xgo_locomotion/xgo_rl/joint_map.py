"""Mapping between policy joint angles (rad, sim convention) and XGO servo registers (u8)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# xgolib "xgolite" MOTOR_LIMIT, in motor degrees, per servo role.
LITE_MOTOR_LIMITS_DEG = {"lower": (-70.0, 50.0), "mid": (-70.0, 90.0), "upper": (-30.0, 30.0)}


@dataclass(frozen=True)
class JointSpec:
    name: str
    register: int  # index into the 15-register 0x50 block
    role: str  # lower | mid | upper
    sign: float
    offset_deg: float  # motor_deg = sign * deg(q_sim) + offset_deg

    @property
    def limits_deg(self) -> tuple[float, float]:
        return LITE_MOTOR_LIMITS_DEG[self.role]


class JointMap:
    def __init__(self, joints: list[JointSpec]):
        self.joints = joints
        self.names = [j.name for j in joints]
        self.registers = np.array([j.register for j in joints])
        self.sign = np.array([j.sign for j in joints], dtype=np.float64)
        self.offset = np.array([j.offset_deg for j in joints], dtype=np.float64)
        lim = np.array([j.limits_deg for j in joints], dtype=np.float64)
        self.lo, self.hi = lim[:, 0], lim[:, 1]
        if sorted(self.registers.tolist()) != self.registers.tolist() or len(
            set(self.registers.tolist())
        ) != len(joints):
            raise ValueError("registers must be unique and increasing (one contiguous write)")

    @classmethod
    def from_config(cls, cfg: list[dict]) -> JointMap:
        return cls([JointSpec(**j) for j in cfg])

    def rad_to_motor_deg(self, q: np.ndarray) -> np.ndarray:
        return self.sign * np.rad2deg(q) + self.offset

    def motor_deg_to_rad(self, deg: np.ndarray) -> np.ndarray:
        return np.deg2rad((deg - self.offset) / self.sign)

    def to_u8(self, q: np.ndarray) -> np.ndarray:
        deg = np.clip(self.rad_to_motor_deg(q), self.lo, self.hi)
        return np.rint((deg - self.lo) / (self.hi - self.lo) * 255).astype(np.uint8)

    def from_u8(self, u8: np.ndarray) -> np.ndarray:
        deg = np.asarray(u8, dtype=np.float64) / 255.0 * (self.hi - self.lo) + self.lo
        return self.motor_deg_to_rad(deg)

    def sim_limits(self) -> tuple[np.ndarray, np.ndarray]:
        """Motor limits expressed as sim joint angles (rad), ordered lo <= hi."""
        a, b = self.motor_deg_to_rad(self.lo), self.motor_deg_to_rad(self.hi)
        return np.minimum(a, b), np.maximum(a, b)

    def quantum_rad(self) -> np.ndarray:
        return np.deg2rad((self.hi - self.lo) / 255.0)
