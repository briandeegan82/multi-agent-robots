"""ONNX policy exported by luwu_mjlab's VelocityOnPolicyRunner (metadata carries the contract)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EXPECTED_OBS = (
    "base_ang_vel",
    "projected_gravity",
    "command",
    "phase",
    "joint_pos",
    "joint_vel",
    "actions",
)


@dataclass(frozen=True)
class PolicyMeta:
    joint_names: list[str]
    default_joint_pos: np.ndarray
    action_scale: float
    observation_names: tuple[str, ...]
    obs_dim: int
    act_dim: int


def _csv(s: str) -> list[str]:
    return [v for v in s.split(",") if v]


def parse_meta(props: dict[str, str], obs_dim: int, act_dim: int) -> PolicyMeta:
    meta = PolicyMeta(
        joint_names=_csv(props["joint_names"]),
        default_joint_pos=np.array([float(v) for v in _csv(props["default_joint_pos"])]),
        action_scale=float(props["action_scale"]),
        observation_names=tuple(_csv(props["observation_names"])),
        obs_dim=obs_dim,
        act_dim=act_dim,
    )
    if meta.observation_names != EXPECTED_OBS:
        raise ValueError(f"unsupported observation terms {meta.observation_names}")
    n = len(meta.joint_names)
    if act_dim != n or obs_dim != 11 + 3 * n or len(meta.default_joint_pos) != n:
        raise ValueError(f"dims obs={obs_dim} act={act_dim} do not match {n} joints")
    return meta


class OnnxPolicy:
    def __init__(self, path: str, threads: int = 1):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(path, opts, providers=["CPUExecutionProvider"])
        inp, out = self.session.get_inputs()[0], self.session.get_outputs()[0]
        self.input_name = inp.name
        props = self.session.get_modelmeta().custom_metadata_map
        self.meta = parse_meta(props, int(inp.shape[-1]), int(out.shape[-1]))

    def __call__(self, obs: np.ndarray) -> np.ndarray:
        x = np.asarray(obs, dtype=np.float32).reshape(1, -1)
        return self.session.run(None, {self.input_name: x})[0][0].astype(np.float64)
