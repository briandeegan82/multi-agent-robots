"""xgo-run: run an exported ONNX locomotion policy on the XGO (or a simulated one)."""

from __future__ import annotations

import argparse
import signal
import sys

import numpy as np

from .config import RobotConfig, load_config
from .controller import Fault, PolicyController
from .driver import XgoDriver
from .policy import OnnxPolicy


def make_sim(cfg: RobotConfig, meta, kind: str):
    from .sim_xgo import FakeSerial, KinematicBackend, MujocoBackend, XgoDeviceModel

    pol_idx = [meta.joint_names.index(n) for n in cfg.joint_map.names]
    q0 = meta.default_joint_pos[pol_idx]
    if kind == "kinematic":
        backend = KinematicBackend(cfg.joint_map, q0)
    else:
        backend = MujocoBackend(cfg.joint_map, q0, dict(zip(meta.joint_names, meta.default_joint_pos)))
    return FakeSerial(XgoDeviceModel(backend)), backend


def open_port(args, cfg: RobotConfig):
    if args.ble:
        from .transport import BleTransport

        return BleTransport(args.ble)
    from .transport import open_serial

    return open_serial(args.port, cfg.baud)


def add_port_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", default="config/xgo_lite_v2.yaml")
    p.add_argument("--port", default="/dev/ttyS4", help="UART device on the Rock Pi 4")
    p.add_argument("--ble", metavar="MAC", help="use BLE instead of UART (slower, ~10-20 Hz)")
    p.add_argument("--sim", choices=["kinematic", "mujoco"], help="use a simulated XGO")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_port_args(p)
    p.add_argument("--policy", required=True)
    p.add_argument("--vx", type=float, default=0.0)
    p.add_argument("--vy", type=float, default=0.0)
    p.add_argument("--wz", type=float, default=0.0)
    p.add_argument("--duration", type=float, default=10.0)
    p.add_argument("--log", help="save per-step obs/actions/targets to this .npz")
    p.add_argument("--allow-uncalibrated", action="store_true")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    policy = OnnxPolicy(args.policy)
    cmd = np.array([args.vx, args.vy, args.wz])
    if args.sim:
        port, backend = make_sim(cfg, policy.meta, args.sim)
        clock_t = [0.0]

        def clock():
            return clock_t[0]

        def advance(dt):
            backend.advance(dt)
            clock_t[0] += dt

        drv = XgoDriver(port)
        ctl = PolicyController(drv, cfg, policy, policy.meta, command=lambda t: cmd, clock=clock)
        sleep = advance
    else:
        if not cfg.calibrated and not args.allow_uncalibrated:
            print("config is not calibrated; run xgo-calibrate first", file=sys.stderr)
            return 2
        drv = XgoDriver(open_port(args, cfg))
        print("firmware:", drv.read_firmware(), "battery:", drv.read_battery())
        ctl = PolicyController(drv, cfg, policy, policy.meta, command=lambda t: cmd)
        sleep = None
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

    rc = 0
    try:
        ctl.stand_up(**({"advance": sleep} if args.sim else {}))
        ctl.run(args.duration, **({"sleep": sleep} if args.sim else {}))
    except Fault as e:
        print("FAULT:", e, file=sys.stderr)
        rc = 1
    except KeyboardInterrupt:
        print("stopped")
    finally:
        cyc = np.asarray(ctl.log.cycle_s)
        if len(cyc):
            print(f"steps {len(cyc)}  cycle mean {cyc.mean() * 1e3:.2f} ms  "
                  f"p95 {np.percentile(cyc, 95) * 1e3:.2f} ms  max {cyc.max() * 1e3:.2f} ms")
        if args.sim == "mujoco":
            print(f"final base height {backend.base_height():.3f} m")
        if args.log:
            ctl.log.save(args.log)
    return rc


if __name__ == "__main__":
    sys.exit(main())
