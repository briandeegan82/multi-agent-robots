from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "xgo_lite_v2.yaml"

# Contract of luwu_mjlab Lite3-Walk-Flat (copied from an exported policy.onnx).
LITE3_META = {
    "joint_names": "FL_hip_joint,FL_thigh_joint,FL_shank_joint,FR_hip_joint,FR_thigh_joint,"
    "FR_shank_joint,RR_hip_joint,RR_thigh_joint,RR_shank_joint,RL_hip_joint,RL_thigh_joint,"
    "RL_shank_joint,mainarm_joint,forearm_joint",
    "default_joint_pos": "0.000,0.950,0.000,0.000,0.950,0.000,0.000,0.950,0.000,0.000,0.950,"
    "0.000,-1.550,1.300",
    "observation_names": "base_ang_vel,projected_gravity,command,phase,joint_pos,joint_vel,actions",
    "action_scale": "0.25",
    "command_names": "twist",
}


def make_linear_policy(path: Path, weight: np.ndarray | None = None, obs_dim=53, act_dim=14):
    """Tiny ONNX policy (actions = obs @ W) with the luwu metadata contract."""
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper, numpy_helper

    w = np.zeros((obs_dim, act_dim), np.float32) if weight is None else weight.astype(np.float32)
    graph = helper.make_graph(
        [helper.make_node("MatMul", ["obs", "W"], ["actions"])],
        "policy",
        [helper.make_tensor_value_info("obs", TensorProto.FLOAT, [1, obs_dim])],
        [helper.make_tensor_value_info("actions", TensorProto.FLOAT, [1, act_dim])],
        [numpy_helper.from_array(w, "W")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 18)])
    model.ir_version = 9
    for k, v in LITE3_META.items():
        model.metadata_props.add(key=k, value=v)
    onnx.save(model, str(path))
    return path


@pytest.fixture
def zero_policy(tmp_path):
    return make_linear_policy(tmp_path / "zero.onnx")
