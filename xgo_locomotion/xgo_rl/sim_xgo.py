"""Hardware-free XGO: a fake device that speaks the real byte protocol over a fake serial port.

Backends provide the robot physics: `KinematicBackend` (first-order servo lag, level body)
needs only numpy; `MujocoBackend` simulates the luwu_mjlab Lite3 model with plain MuJoCo.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from . import protocol as P
from .joint_map import JointMap

TYPE_REPLY = 0x12
ARM_NEUTRAL_U8 = 128


def lite3_xml_path() -> Path:
    root = os.environ.get("LUWU_MJLAB_DIR", str(Path(__file__).parents[1] / "train" / "luwu_mjlab"))
    return Path(root) / "src" / "assets" / "robots" / "lite3" / "xmls" / "lite3.xml"


class KinematicBackend:
    def __init__(self, joint_map: JointMap, q0: np.ndarray, tau: float = 0.03):
        self.jm, self.tau = joint_map, tau
        self.q = np.asarray(q0, dtype=np.float64).copy()
        self.target_u8 = self.jm.to_u8(self.q)

    def set_target_u8(self, idx: np.ndarray, values: np.ndarray) -> None:
        self.target_u8[idx] = values

    def joint_pos(self) -> np.ndarray:
        return self.q

    def imu(self):
        return (0.0, 0.0, 9.8), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    def advance(self, dt: float) -> None:
        target = self.jm.from_u8(self.target_u8)
        self.q += (target - self.q) * (1.0 - np.exp(-dt / self.tau))


def _quat_to_rpy(w, x, y, z) -> tuple[float, float, float]:
    roll = np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = np.arcsin(np.clip(2 * (w * y - z * x), -1.0, 1.0))
    yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return float(roll), float(pitch), float(yaw)


class MujocoBackend:
    """Lite3 MJCF from luwu_mjlab with the Lite3-Walk-Flat collision setup (feet-only contacts)."""

    def __init__(self, joint_map: JointMap, q0: np.ndarray, default_full: dict[str, float],
                 xml: str | Path | None = None, timestep: float = 0.004, base_z: float = 0.10):
        import mujoco

        self.mj = mujoco
        spec = mujoco.MjSpec.from_file(str(xml or lite3_xml_path()))
        spec.option.timestep = timestep
        for g in spec.geoms:
            g.contype, g.conaffinity = 0, 0
            if g.name.endswith("_shank_collision"):
                g.conaffinity, g.condim, g.priority = 1, 3, 1
                g.friction = [0.6, 0.005, 0.0001]
                g.solimp = [0.9, 0.95, 0.023, 0.5, 2.0]
        spec.worldbody.add_geom(name="floor", type=mujoco.mjtGeom.mjGEOM_PLANE,
                                size=[10, 10, 0.1], contype=1, conaffinity=0)
        self.model = spec.compile()
        self.data = mujoco.MjData(self.model)
        self.jm = joint_map
        m = self.model
        self.qadr = np.array([m.joint(n).qposadr[0] for n in joint_map.names])
        self.dadr = np.array([m.joint(n).dofadr[0] for n in joint_map.names])
        jnt_of_act = {m.joint(int(m.actuator_trnid[a, 0])).name: a for a in range(m.nu)}
        self.act = np.array([jnt_of_act[n] for n in joint_map.names])
        d = self.data
        d.qpos[:3] = [0.0, 0.0, base_z]
        d.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
        for name, val in default_full.items():
            d.qpos[m.joint(name).qposadr[0]] = val
            if name in jnt_of_act:
                d.ctrl[jnt_of_act[name]] = val
        d.qpos[self.qadr] = q0
        d.ctrl[self.act] = q0
        mujoco.mj_forward(m, d)
        self.target_u8 = self.jm.to_u8(np.asarray(q0))

    def set_target_u8(self, idx: np.ndarray, values: np.ndarray) -> None:
        self.target_u8[idx] = values
        self.data.ctrl[self.act] = self.jm.from_u8(self.target_u8)

    def joint_pos(self) -> np.ndarray:
        return self.data.qpos[self.qadr].copy()

    def joint_vel(self) -> np.ndarray:
        return self.data.qvel[self.dadr].copy()

    def sensor(self, name: str) -> np.ndarray:
        s = self.model.sensor(name)
        return self.data.sensordata[s.adr[0] : s.adr[0] + s.dim[0]].copy()

    def base_quat(self) -> np.ndarray:
        return self.data.qpos[3:7].copy()

    def projected_gravity(self) -> np.ndarray:
        w, x, y, z = self.base_quat()
        mat = np.zeros(9)
        self.mj.mju_quat2Mat(mat, np.array([w, x, y, z]))
        return mat.reshape(3, 3).T @ np.array([0.0, 0.0, -1.0])

    def imu(self):
        rpy = np.rad2deg(_quat_to_rpy(*self.base_quat()))
        gyro = np.rad2deg(self.sensor("imu_ang_vel"))
        return tuple(self.sensor("imu_accel")), tuple(gyro), tuple(rpy)

    def advance(self, dt: float) -> None:
        for _ in range(max(round(dt / self.model.opt.timestep), 1)):
            self.mj.mj_step(self.model, self.data)

    def base_height(self) -> float:
        return float(self.data.qpos[2])


class XgoDeviceModel:
    """Answers protocol frames like the XGO firmware (subset used by the runtime)."""

    def __init__(self, backend, firmware: str = "LSIM-1.0"):
        self.backend = backend
        self.firmware = firmware.encode()[:10].ljust(10, b"\0")
        self.reg_of_joint = backend.jm.registers
        self.loaded = True
        self.resets = 0

    def motor_u8(self) -> bytes:
        regs = np.full(P.N_MOTOR_REGS, ARM_NEUTRAL_U8, dtype=np.uint8)
        regs[self.reg_of_joint] = self.backend.jm.to_u8(self.backend.joint_pos())
        return bytes(regs)

    def handle(self, f: P.Frame) -> bytes | None:
        if f.frame_type == P.TYPE_READ:
            n = f.data[0]
            if f.addr == P.ADDR_MOTOR:
                payload = self.motor_u8()[:n]
            elif f.addr == P.ADDR_IMU:
                payload = P.encode_imu(*self.backend.imu())[:n]
            elif f.addr == P.ADDR_RPY:
                payload = P.encode_imu(*self.backend.imu())[12:24][:n]
            elif f.addr == P.ADDR_FIRMWARE:
                payload = self.firmware[:n]
            elif f.addr == P.ADDR_BATTERY:
                payload = bytes([87])[:n]
            else:
                return None
            return P.encode(TYPE_REPLY, f.addr, payload)
        if P.ADDR_MOTOR <= f.addr < P.ADDR_MOTOR + P.N_MOTOR_REGS:
            first = f.addr - P.ADDR_MOTOR
            regs = np.arange(first, first + len(f.data))
            idx = [int(np.where(self.reg_of_joint == r)[0][0]) for r in regs
                   if r in self.reg_of_joint]
            vals = [f.data[i] for i, r in enumerate(regs) if r in self.reg_of_joint]
            self.backend.set_target_u8(np.array(idx, dtype=int), np.array(vals, dtype=np.uint8))
        elif f.addr == P.ADDR_ACTION and f.data[:1] == bytes([P.ACTION_RESET]):
            self.resets += 1
        elif f.addr == P.ADDR_LOAD:
            self.loaded = f.data[:1] == bytes([P.LOAD_ALL])
        return None


class FakeSerial:
    """pyserial-like byte stream into an XgoDeviceModel; counts wire bytes for timing estimates."""

    def __init__(self, device: XgoDeviceModel):
        self.device = device
        self.parser = P.FrameParser()
        self.rx = bytearray()
        self.bytes_tx = 0

    def write(self, data: bytes) -> int:
        self.bytes_tx += len(data)
        for f in self.parser.feed(bytes(data)):
            reply = self.device.handle(f)
            if reply:
                self.rx.extend(reply)
        return len(data)

    @property
    def in_waiting(self) -> int:
        return len(self.rx)

    def read(self, n: int = 1) -> bytes:
        out = bytes(self.rx[:n])
        del self.rx[:n]
        return out

    def reset_input_buffer(self) -> None:
        self.rx.clear()

    def close(self) -> None:
        pass
