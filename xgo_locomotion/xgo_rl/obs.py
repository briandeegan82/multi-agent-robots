"""Actor observation, built exactly as luwu_mjlab's velocity task (flat, no height scan)."""

from __future__ import annotations

import numpy as np


def projected_gravity_from_rp(roll: float, pitch: float) -> np.ndarray:
    """Unit gravity in the body frame for ZYX (yaw-pitch-roll) Euler angles in rad."""
    cp = np.cos(pitch)
    return np.array([np.sin(pitch), -cp * np.sin(roll), -cp * np.cos(roll)])


def phase_obs(t: float, period: float, command: np.ndarray, stand_threshold: float) -> np.ndarray:
    if np.linalg.norm(command) < stand_threshold:
        return np.zeros(2)
    x = (t % period) / period * 2.0 * np.pi
    return np.array([np.sin(x), np.cos(x)])


def build_obs(
    ang_vel: np.ndarray,
    gravity: np.ndarray,
    command: np.ndarray,
    phase: np.ndarray,
    joint_pos_rel: np.ndarray,
    joint_vel: np.ndarray,
    last_action: np.ndarray,
) -> np.ndarray:
    return np.concatenate(
        [ang_vel, gravity, command, phase, joint_pos_rel, joint_vel, last_action]
    ).astype(np.float32)
