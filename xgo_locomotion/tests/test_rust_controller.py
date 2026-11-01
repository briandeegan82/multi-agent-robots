"""Rust controller (xgo_controller) against the simulated XGO over a pty.

Checks the Rust binary end to end over the real byte protocol, and that its observations and
actions match the Python reference (obs builder verified against luwu_mjlab in test_mjlab_parity).
Build first: `cargo build --release --manifest-path xgo_controller/Cargo.toml`.
"""

import subprocess

import numpy as np
import pytest

from xgo_rl.config import load_config
from xgo_rl.obs import build_obs, phase_obs, projected_gravity_from_rp
from xgo_rl.policy import OnnxPolicy
from xgo_rl.pty_sim import PtySim, make_backend
from xgo_rl.sim_xgo import lite3_xml_path

from .conftest import CONFIG, ROOT, make_linear_policy

BIN = ROOT / "xgo_controller" / "target" / "release" / "xgo_controller"
pytestmark = pytest.mark.skipif(not BIN.exists(), reason="xgo_controller not built")


def run_rust(port, policy, log, *extra, duration=2.0, vx=0.2):
    return subprocess.run(
        [str(BIN), "--config", str(CONFIG), "--port", port, "run", "--policy", str(policy),
         "--vx", str(vx), "--duration", str(duration), "--log", str(log), "--allow-uncalibrated",
         *extra],
        check=False, capture_output=True, text=True, timeout=60,
    )


def python_reference(log, policy_path):
    cfg = load_config(CONFIG)
    pol = OnnxPolicy(str(policy_path))
    meta = pol.meta
    jm, n, m = cfg.joint_map, len(cfg.joint_map.names), len(meta.joint_names)
    idx = [meta.joint_names.index(j) for j in jm.names]
    rows = np.loadtxt(log, delimiter=",", ndmin=2)
    t, raw, gyro, rpy, cmd = (rows[:, 0], rows[:, 1:1 + n], rows[:, 1 + n:4 + n],
                              rows[:, 4 + n:7 + n], rows[:, 7 + n:10 + n])
    o0 = 10 + n
    obs_rs = rows[:, o0:o0 + 11 + 3 * m]
    act_rs = rows[:, o0 + 11 + 3 * m:o0 + 11 + 4 * m]
    q_full = np.array(meta.default_joint_pos, float)
    dq_full = np.zeros(m)
    last, prev = np.zeros(m), None
    obs_py, act_py = [], []
    for k in range(len(rows)):
        q = jm.from_u8(raw[k].astype(np.uint8))
        dt = 1.0 / cfg.control_hz if prev is None else max(t[k] - prev[0], 1e-3)
        dq_full[idx] = 0.0 if prev is None else (q - prev[1]) / dt
        q_full[idx] = q
        prev = (t[k], q)
        r, p = np.radians(rpy[k, :2])
        o = build_obs(np.radians(gyro[k]), projected_gravity_from_rp(r, p), cmd[k],
                      phase_obs(t[k], cfg.phase_period, cmd[k], cfg.stand_threshold),
                      q_full - meta.default_joint_pos, dq_full, last)
        obs_py.append(o)
        last = act_rs[k]  # what the robot actually fed back
        act_py.append(np.ravel(pol(obs_rs[k].astype(np.float32))))
    return obs_rs, np.array(obs_py), act_rs, np.array(act_py)


@pytest.mark.parametrize("sim", ["kinematic", "mujoco"])
def test_rust_controller_closed_loop_matches_python(sim, tmp_path):
    if sim == "mujoco":
        pytest.importorskip("mujoco")
        if not lite3_xml_path().exists():
            pytest.skip("luwu_mjlab not cloned")
    rng = np.random.default_rng(0)
    policy = make_linear_policy(tmp_path / "p.onnx", (0.02 * rng.standard_normal((53, 14))).astype(np.float32))
    log = tmp_path / "run.csv"
    with PtySim(make_backend(sim, str(CONFIG), str(policy))) as srv:
        res = run_rust(srv.path, policy, log)
        resets = srv.device.resets
    assert res.returncode == 0, res.stderr
    assert resets == 1, "safe_stop must reset the robot"
    obs_rs, obs_py, act_rs, act_py = python_reference(log, policy)
    assert len(obs_rs) >= 80, res.stdout
    np.testing.assert_allclose(obs_rs, obs_py, atol=1e-5)
    np.testing.assert_allclose(act_rs, act_py, atol=1e-5)


def test_rust_tilt_fault_resets(tmp_path):
    policy = make_linear_policy(tmp_path / "p.onnx", np.zeros((53, 14), np.float32))
    backend = make_backend("kinematic", str(CONFIG), str(policy))
    backend.imu = lambda: ((0, 0, 9.8), (0, 0, 0), (50.0, 0.0, 0.0))
    with PtySim(backend) as srv:
        res = run_rust(srv.path, policy, tmp_path / "f.csv", "--no-stand-up")
        resets = srv.device.resets
    assert res.returncode != 0 and "tilt" in res.stderr
    assert resets == 1


def test_rust_refuses_uncalibrated(tmp_path):
    policy = make_linear_policy(tmp_path / "p.onnx", np.zeros((53, 14), np.float32))
    with PtySim(make_backend("kinematic", str(CONFIG), str(policy))) as srv:
        res = subprocess.run([str(BIN), "--config", str(CONFIG), "--port", srv.path, "run",
                              "--policy", str(policy)], check=False, capture_output=True, text=True, timeout=30)
    assert res.returncode != 0 and "not calibrated" in res.stderr
