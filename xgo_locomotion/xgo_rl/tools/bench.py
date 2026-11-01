"""xgo-bench: measure the achievable control rate over the real link (UART or BLE).

Each cycle does what the policy loop does: read 15 motor registers, read the IMU block,
write 12 leg targets (the current pose, so the robot does not move).
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np

from ..cli import add_port_args, open_port
from ..config import load_config
from ..driver import XgoDriver, XgoTimeout


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_port_args(p)
    p.add_argument("--cycles", type=int, default=500)
    p.add_argument("--imu", choices=["imu65", "rpy62", "none"], default=None)
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    imu = args.imu or cfg.imu.source

    if args.sim:
        from ..sim_xgo import FakeSerial, KinematicBackend, XgoDeviceModel

        port = FakeSerial(XgoDeviceModel(KinematicBackend(cfg.joint_map, np.zeros(12))))
    else:
        port = open_port(args, cfg)
    drv = XgoDriver(port, read_timeout=0.1)
    print("firmware:", drv.read_firmware(), " battery:", drv.read_battery())
    hold = drv.read_motors_u8()[:12]
    times, timeouts = [], 0
    for _ in range(args.cycles):
        t0 = time.perf_counter()
        try:
            drv.read_motors_u8()
            if imu == "imu65":
                drv.read_imu()
            elif imu == "rpy62":
                drv.read_rpy()
        except XgoTimeout:
            timeouts += 1
            continue
        drv.write_motors_u8(0, hold)
        times.append(time.perf_counter() - t0)
    t = np.asarray(times) * 1e3
    if len(t) == 0:
        print("all reads timed out")
        return 1
    bytes_per_cycle = (drv.bytes_tx + drv.bytes_rx) / max(args.cycles, 1)
    print(f"cycles {len(t)}/{args.cycles}  timeouts {timeouts}  bytes/cycle {bytes_per_cycle:.0f}")
    print(f"cycle ms: mean {t.mean():.2f}  p50 {np.median(t):.2f}  p95 {np.percentile(t, 95):.2f}"
          f"  max {t.max():.2f}")
    hz = 1e3 / np.percentile(t, 95)
    print(f"sustainable rate (p95) ~{hz:.0f} Hz; policy needs {cfg.control_hz:.0f} Hz "
          f"plus ~1-2 ms inference -> {'OK' if hz > cfg.control_hz * 1.25 else 'TOO SLOW'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
