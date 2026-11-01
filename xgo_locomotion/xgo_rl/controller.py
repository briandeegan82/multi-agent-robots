"""Policy control loop: read XGO state -> observation -> ONNX -> clamped servo targets."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .config import RobotConfig
from .driver import XgoDriver, XgoTimeout
from .obs import build_obs, phase_obs, projected_gravity_from_rp
from .policy import PolicyMeta


class Fault(RuntimeError):
    pass


@dataclass
class StepLog:
    t: list[float] = field(default_factory=list)
    obs: list[np.ndarray] = field(default_factory=list)
    action: list[np.ndarray] = field(default_factory=list)
    target: list[np.ndarray] = field(default_factory=list)
    q: list[np.ndarray] = field(default_factory=list)
    cycle_s: list[float] = field(default_factory=list)

    def save(self, path: str) -> None:
        np.savez(path, **{k: np.asarray(v) for k, v in self.__dict__.items()})


class PolicyController:
    def __init__(self, driver: XgoDriver, cfg: RobotConfig, policy, meta: PolicyMeta,
                 command=lambda t: np.zeros(3), clock=time.monotonic):
        self.driver, self.cfg, self.policy, self.meta = driver, cfg, policy, meta
        self.command, self.clock = command, clock
        self.dt = 1.0 / cfg.control_hz
        jm = cfg.joint_map
        missing = set(jm.names) - set(meta.joint_names)
        if missing:
            raise ValueError(f"config joints not in policy: {missing}")
        # Policy index of each mapped joint (mapped joints are in register order).
        self.pol_idx = np.array([meta.joint_names.index(n) for n in jm.names])
        self.default = meta.default_joint_pos
        lo, hi = jm.sim_limits()
        margin = np.deg2rad(cfg.safety.joint_margin_deg)
        self.q_lo, self.q_hi = lo + margin, hi - margin
        self.first_reg = int(jm.registers[0])
        self.n_regs = int(jm.registers[-1]) + 1
        if not np.array_equal(jm.registers, np.arange(self.first_reg, self.n_regs)):
            raise ValueError("mapped registers must be contiguous")
        self.reset_state()
        self.log = StepLog()

    def reset_state(self) -> None:
        n = len(self.meta.joint_names)
        self.last_action = np.zeros(n)
        self.q_full = self.default.copy()
        self.dq_full = np.zeros(n)
        self.prev_q = None
        self.prev_rpy = None
        self.prev_t = None
        self.target = None
        self.read_failures = 0
        self.t0 = None

    # State.
    def read_state(self, t: float):
        cfg = self.cfg
        raw = self.driver.read_motors_u8(self.n_regs)[self.first_reg:]
        q = self.cfg.joint_map.from_u8(raw)
        if cfg.imu.source == "imu65":
            s = self.driver.read_imu()
            rpy = np.deg2rad(np.array(s.rpy_deg))
            g = np.deg2rad(np.array(s.gyro_dps))[cfg.imu.gyro_axes] * cfg.imu.gyro_sign
        else:
            rpy = np.deg2rad(np.array(self.driver.read_rpy()))
            g = None
        roll, pitch = rpy[0] * cfg.imu.roll_sign, rpy[1] * cfg.imu.pitch_sign
        dt = self.dt if self.prev_t is None else max(t - self.prev_t, 1e-3)
        if g is None:
            g = np.zeros(3) if self.prev_rpy is None else (rpy - self.prev_rpy) / dt
        dq = np.zeros_like(q) if self.prev_q is None else (q - self.prev_q) / dt
        a = cfg.joint_vel_ema
        dq_mapped = a * dq + (1 - a) * self.dq_full[self.pol_idx]
        self.prev_q, self.prev_rpy, self.prev_t = q, rpy, t
        return q, dq_mapped, np.array([roll, pitch]), g

    def check_safety(self, rp: np.ndarray) -> None:
        if np.any(np.abs(np.rad2deg(rp)) > self.cfg.safety.tilt_limit_deg):
            raise Fault(f"tilt {np.rad2deg(rp).round(1)} deg exceeds limit")

    def write_targets(self, q_target: np.ndarray) -> np.ndarray:
        q_target = np.clip(q_target, self.q_lo, self.q_hi)
        if self.target is not None:
            m = self.cfg.safety.max_step_rad
            q_target = np.clip(q_target, self.target - m, self.target + m)
        self.target = q_target
        self.driver.write_motors_u8(self.first_reg, self.cfg.joint_map.to_u8(q_target))
        return q_target

    def step(self, t: float | None = None) -> np.ndarray:
        t = self.clock() if t is None else t
        if self.t0 is None:
            self.t0 = t
        try:
            q, dq, rp, ang_vel = self.read_state(t)
            self.read_failures = 0
        except XgoTimeout:
            self.read_failures += 1
            if self.read_failures >= self.cfg.safety.max_read_failures:
                raise Fault("too many consecutive read timeouts") from None
            return self.target
        self.check_safety(rp)
        self.q_full[self.pol_idx] = q
        self.dq_full[self.pol_idx] = dq
        cmd = np.asarray(self.command(t - self.t0), dtype=np.float64)
        obs = build_obs(
            ang_vel,
            projected_gravity_from_rp(rp[0], rp[1]),
            cmd,
            phase_obs(t - self.t0, self.cfg.phase_period, cmd, self.cfg.stand_threshold),
            self.q_full - self.default,
            self.dq_full,
            self.last_action,
        )
        action = self.policy(obs)
        self.last_action = action
        q_target = self.default + self.meta.action_scale * action
        sent = self.write_targets(q_target[self.pol_idx])
        self.log.t.append(t - self.t0)
        self.log.obs.append(obs)
        self.log.action.append(action)
        self.log.target.append(sent)
        self.log.q.append(q)
        return sent

    def stand_up(self, sleep=time.sleep, advance=None) -> None:
        """Ramp from the measured pose to the policy default pose."""
        raw = self.driver.read_motors_u8(self.n_regs)[self.first_reg:]
        q0 = self.cfg.joint_map.from_u8(raw)
        q1 = np.clip(self.default[self.pol_idx], self.q_lo, self.q_hi)
        n = max(int(self.cfg.stand_up_s / self.dt), 1)
        for i in range(1, n + 1):
            self.target = None
            self.write_targets(q0 + (q1 - q0) * i / n)
            (advance or sleep)(self.dt)

    def safe_stop(self) -> None:
        mode = self.cfg.safety.on_fault
        if mode == "reset":
            self.driver.reset()
        elif mode == "unload":
            self.driver.unload_all()

    def run(self, duration: float, sleep=time.sleep) -> None:
        self.reset_state()
        next_t = self.clock()
        end = next_t + duration
        try:
            while self.clock() < end:
                t = self.clock()
                self.step(t)
                self.log.cycle_s.append(self.clock() - t)
                next_t += self.dt
                delay = next_t - self.clock()
                if delay > 0:
                    sleep(delay)
                else:
                    next_t = self.clock()
        finally:
            self.safe_stop()
