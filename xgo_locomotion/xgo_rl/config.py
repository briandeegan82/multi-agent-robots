from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .joint_map import JointMap


@dataclass
class ImuConfig:
    source: str = "imu65"  # imu65: gyro + rpy block; rpy62: rpy only, gyro by differencing
    gyro_axes: list[int] = field(default_factory=lambda: [0, 1, 2])
    gyro_sign: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    roll_sign: float = 1.0
    pitch_sign: float = 1.0


@dataclass
class SafetyConfig:
    tilt_limit_deg: float = 35.0
    joint_margin_deg: float = 2.0
    max_step_rad: float = 0.15
    max_read_failures: int = 3
    on_fault: str = "reset"  # reset | unload | hold


@dataclass
class RobotConfig:
    joint_map: JointMap
    calibrated: bool
    imu: ImuConfig
    safety: SafetyConfig
    control_hz: float = 50.0
    phase_period: float = 0.4
    stand_threshold: float = 0.1
    stand_up_s: float = 2.0
    joint_vel_ema: float = 1.0
    baud: int = 115200


def load_config(path: str | Path) -> RobotConfig:
    raw = yaml.safe_load(Path(path).read_text())
    return RobotConfig(
        joint_map=JointMap.from_config(raw["joints"]),
        calibrated=bool(raw.get("calibrated", False)),
        imu=ImuConfig(**raw.get("imu", {})),
        safety=SafetyConfig(**raw.get("safety", {})),
        **raw.get("control", {}),
    )
