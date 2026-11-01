"""Runtime against the fake XGO: byte protocol end to end, with kinematic and MuJoCo physics."""

import os
from pathlib import Path

import numpy as np
import pytest

from xgo_rl.config import load_config
from xgo_rl.controller import Fault, PolicyController
from xgo_rl.driver import XgoDriver
from xgo_rl.policy import OnnxPolicy
from xgo_rl.sim_xgo import (
    FakeSerial,
    KinematicBackend,
    MujocoBackend,
    XgoDeviceModel,
    lite3_xml_path,
)

from .conftest import CONFIG, ROOT


class SimClock:
    def __init__(self, backend):
        self.t, self.backend = 0.0, backend

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.backend.advance(dt)
        self.t += dt


def make(policy_path, backend_kind="kinematic", cmd=(0.0, 0.0, 0.0)):
    cfg = load_config(CONFIG)
    policy = OnnxPolicy(str(policy_path))
    meta = policy.meta
    pol_idx = [meta.joint_names.index(n) for n in cfg.joint_map.names]
    q0 = meta.default_joint_pos[pol_idx]
    if backend_kind == "kinematic":
        backend = KinematicBackend(cfg.joint_map, q0)
    else:
        if not lite3_xml_path().exists():
            pytest.skip("luwu_mjlab not cloned (train/setup_train_env.sh or LUWU_MJLAB_DIR)")
        pytest.importorskip("mujoco")
        backend = MujocoBackend(cfg.joint_map, q0, dict(zip(meta.joint_names, meta.default_joint_pos)))
    port = FakeSerial(XgoDeviceModel(backend))
    clock = SimClock(backend)
    drv = XgoDriver(port)
    ctl = PolicyController(drv, cfg, policy, meta, command=lambda t: np.array(cmd), clock=clock)
    return ctl, backend, clock, port


def test_kinematic_loop_holds_default_pose_and_fits_uart_budget(zero_policy):
    ctl, _backend, clock, port = make(zero_policy)
    ctl.stand_up(advance=clock.advance)
    ctl.run(2.0, sleep=clock.advance)
    assert len(ctl.log.t) == 100
    np.testing.assert_allclose(ctl.log.target[-1], ctl.default[ctl.pol_idx],
                               atol=ctl.cfg.joint_map.quantum_rad().max())
    assert port.device.resets == 1  # safe_stop -> firmware reset
    bytes_per_step = (ctl.driver.bytes_tx + ctl.driver.bytes_rx) / (len(ctl.log.t) + 100)
    wire_ms = bytes_per_step * 10 / 115200 * 1e3
    assert wire_ms < 10.0, f"{bytes_per_step:.0f} B/step = {wire_ms:.1f} ms at 115200 baud"


def test_obs_layout_matches_policy_contract(zero_policy):
    ctl, _, clock, _ = make(zero_policy, cmd=(0.3, 0.0, 0.0))
    for _ in range(5):
        ctl.step()
        clock.advance(ctl.dt)
    obs = ctl.log.obs[-1]
    assert obs.shape == (53,)
    np.testing.assert_allclose(obs[3:6], [0, 0, -1], atol=1e-6)  # level body gravity
    np.testing.assert_allclose(obs[6:9], [0.3, 0, 0])
    assert np.linalg.norm(obs[9:11]) == pytest.approx(1.0)  # phase active when moving
    np.testing.assert_allclose(obs[11:25], 0, atol=0.02)  # joint_pos_rel at default
    assert np.all(obs[23:25] == 0) and np.all(obs[37:39] == 0)  # arm held at default


def test_tilt_fault_triggers_safe_stop(zero_policy):
    ctl, backend, clock, port = make(zero_policy)
    backend.imu = lambda: ((0, 0, 9.8), (0, 0, 0), (50.0, 0.0, 0.0))
    with pytest.raises(Fault):
        ctl.run(1.0, sleep=clock.advance)
    assert port.device.resets == 1


def test_read_timeouts_fault(zero_policy):
    ctl, _, clock, port = make(zero_policy)
    port.device.handle = lambda f: None  # robot stops answering
    ctl.driver.read_timeout = 0.0
    with pytest.raises(Fault):
        ctl.run(1.0, sleep=clock.advance)


def test_step_limit_and_joint_clamp(tmp_path):
    from .conftest import make_linear_policy

    w = np.zeros((53, 14), np.float32)
    w[5, :] = 100.0  # gravity z = -1 -> action -100 -> far outside limits
    ctl, _, clock, _ = make(make_linear_policy(tmp_path / "big.onnx", w))
    ctl.step()
    first = ctl.log.target[0]
    clock.advance(ctl.dt)
    ctl.step()
    assert np.all(np.abs(ctl.log.target[1] - first) <= ctl.cfg.safety.max_step_rad + 1e-9)
    for _ in range(100):
        clock.advance(ctl.dt)
        ctl.step()
    assert np.all(ctl.log.target[-1] >= ctl.q_lo - 1e-9)


def test_mujoco_default_pose_stands_and_obs_match_sim_state(zero_policy):
    ctl, backend, clock, _ = make(zero_policy, "mujoco")
    for _ in range(25):
        clock.advance(ctl.dt)  # settle onto the floor
    for _ in range(150):
        ctl.step()
        clock.advance(ctl.dt)
    assert backend.base_height() > 0.05
    obs = ctl.log.obs[-1]
    np.testing.assert_allclose(obs[3:6], backend.projected_gravity(), atol=1e-3)
    q_rel = backend.joint_pos() - ctl.default[ctl.pol_idx]
    np.testing.assert_allclose(obs[11:25][ctl.pol_idx], q_rel,
                               atol=ctl.cfg.joint_map.quantum_rad().max())


POLICY = os.environ.get("XGO_POLICY", str(ROOT / "policies" / "latest.onnx"))


@pytest.mark.skipif(not Path(POLICY).exists(), reason="no trained policy (set XGO_POLICY)")
def test_trained_policy_runs_in_mujoco():
    ctl, _backend, clock, _ = make(POLICY, "mujoco", cmd=(0.2, 0.0, 0.0))
    ctl.stand_up(advance=clock.advance)
    try:
        ctl.run(3.0, sleep=clock.advance)
    except Fault:
        pass  # an untrained smoke policy may fall; this test checks the plumbing only
    assert len(ctl.log.t) > 0 and np.all(np.isfinite(ctl.log.action))
