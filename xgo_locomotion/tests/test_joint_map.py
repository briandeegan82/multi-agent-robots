import numpy as np

from xgo_rl.config import load_config
from xgo_rl.joint_map import JointMap, JointSpec

from .conftest import CONFIG


def test_config_loads_and_is_uncalibrated_by_default():
    cfg = load_config(CONFIG)
    assert len(cfg.joint_map.names) == 12
    assert cfg.joint_map.registers.tolist() == list(range(12))
    assert not cfg.calibrated


def test_roundtrip_within_one_count():
    jm = JointMap([
        JointSpec("a", 0, "lower", -1.0, 10.0),
        JointSpec("b", 1, "mid", 1.0, -20.0),
        JointSpec("c", 2, "upper", 1.0, 0.0),
    ])
    lo, hi = jm.sim_limits()
    rng = np.random.default_rng(0)
    for _ in range(200):
        q = rng.uniform(lo, hi)
        err = np.abs(jm.from_u8(jm.to_u8(q)) - q)
        assert np.all(err <= jm.quantum_rad() / 2 + 1e-9)


def test_targets_clamped_to_motor_limits():
    jm = JointMap([JointSpec("c", 0, "upper", 1.0, 0.0)])
    assert jm.to_u8(np.array([np.deg2rad(90)]))[0] == 255
    assert jm.to_u8(np.array([np.deg2rad(-90)]))[0] == 0
