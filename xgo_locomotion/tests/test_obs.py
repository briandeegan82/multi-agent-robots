import numpy as np
import pytest

from xgo_rl.obs import phase_obs, projected_gravity_from_rp
from xgo_rl.policy import OnnxPolicy, parse_meta

from .conftest import LITE3_META


def _rot_zyx(roll, pitch, yaw):
    cr, sr, cp, sp, cy, sy = np.cos(roll), np.sin(roll), np.cos(pitch), np.sin(pitch), np.cos(
        yaw), np.sin(yaw)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return rz @ ry @ rx


@pytest.mark.parametrize("rpy", [(0.0, 0.0, 0.0), (0.3, -0.2, 1.0), (-0.5, 0.4, -2.0)])
def test_projected_gravity_matches_rotation(rpy):
    expected = _rot_zyx(*rpy).T @ np.array([0, 0, -1.0])
    np.testing.assert_allclose(projected_gravity_from_rp(rpy[0], rpy[1]), expected, atol=1e-12)


def test_phase_zero_when_standing():
    assert np.all(phase_obs(0.13, 0.4, np.array([0.05, 0, 0]), 0.1) == 0)
    np.testing.assert_allclose(phase_obs(0.1, 0.4, np.array([0.3, 0, 0]), 0.1), [1.0, 0.0],
                               atol=1e-12)


def test_meta_contract_checks():
    meta = parse_meta(LITE3_META, 53, 14)
    assert meta.joint_names[0] == "FL_hip_joint" and meta.action_scale == 0.25
    with pytest.raises(ValueError):
        parse_meta(LITE3_META, 54, 14)
    with pytest.raises(ValueError):
        parse_meta({**LITE3_META, "observation_names": "base_ang_vel"}, 53, 14)


def test_onnx_policy_loads(zero_policy):
    p = OnnxPolicy(str(zero_policy))
    assert p.meta.obs_dim == 53
    np.testing.assert_array_equal(p(np.ones(53)), np.zeros(14))
