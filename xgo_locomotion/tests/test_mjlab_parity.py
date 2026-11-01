"""Opt-in (XGO_MJLAB_PARITY=1): our observation builder vs luwu_mjlab's own actor observation.

Needs the training venv (mjlab, torch) and the luwu_mjlab clone; compiles Warp kernels (~1 min
on CPU the first time).
"""

import os
import sys

import numpy as np
import pytest

from xgo_rl.obs import build_obs, phase_obs, projected_gravity_from_rp
from xgo_rl.sim_xgo import _quat_to_rpy, lite3_xml_path

pytestmark = pytest.mark.skipif(os.environ.get("XGO_MJLAB_PARITY") != "1",
                                reason="set XGO_MJLAB_PARITY=1")


def test_actor_obs_parity():
    torch = pytest.importorskip("torch")
    luwu = str(lite3_xml_path().parents[5])
    sys.path.insert(0, luwu)
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    import mjlab.tasks  # noqa: F401
    import src.tasks  # noqa: F401
    from mjlab.envs import ManagerBasedRlEnv
    from mjlab.tasks.registry import load_env_cfg

    cfg = load_env_cfg("Lite3-Walk-Flat", play=True)
    cfg.scene.num_envs = 1
    env = ManagerBasedRlEnv(cfg=cfg, device="cpu")
    env.reset()
    robot = env.scene["robot"]
    assert list(robot.joint_names)[:12] == [
        f"{leg}_{j}_joint" for leg in ("FL", "FR", "RR", "RL") for j in ("hip", "thigh", "shank")
    ]
    gen = torch.Generator().manual_seed(0)
    for k in range(20):
        action = 0.3 * torch.randn((1, env.action_manager.total_action_dim), generator=gen)
        obs, *_ = env.step(action)
        if k < 5:
            continue
        d = robot.data
        cmd = env.command_manager.get_command("twist")[0].numpy()
        t = float(env.episode_length_buf[0]) * env.step_dt
        quat = d.root_link_quat_w[0].numpy()
        roll, pitch, _ = _quat_to_rpy(*quat)
        mine = build_obs(
            env.scene["robot/imu_ang_vel"].data[0].numpy(),
            projected_gravity_from_rp(roll, pitch),
            cmd,
            phase_obs(t, 0.4, cmd, 0.1),
            (d.joint_pos - d.default_joint_pos)[0].numpy(),
            (d.joint_vel - d.default_joint_vel)[0].numpy(),
            env.action_manager.action[0].numpy(),
        )
        np.testing.assert_allclose(mine, obs["actor"][0].numpy(), atol=1e-4)
