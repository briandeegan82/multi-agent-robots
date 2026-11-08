"""Simulated XGO behind a pseudo-terminal, so any client (e.g. the Rust controller) talks to it
like the real UART. Physics advances in real time.

    xgo-sim-serve --sim mujoco --policy policies/latest.onnx   # prints the /dev/pts/N path
"""

from __future__ import annotations

import argparse
import os
import select
import threading
import time
import tty
from typing import Self

from .config import load_config
from .policy import OnnxPolicy
from .sim_xgo import FakeSerial, KinematicBackend, MujocoBackend, XgoDeviceModel


class PtySim:
    def __init__(self, backend, physics_dt: float = 0.004):
        self.backend = backend
        self.serial = FakeSerial(XgoDeviceModel(backend))
        self.device = self.serial.device
        self.master, self.slave = os.openpty()
        tty.setraw(self.slave)
        self.path = os.ttyname(self.slave)
        self.physics_dt = physics_dt
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._threads = [threading.Thread(target=f, daemon=True) for f in (self._io, self._physics)]

    def start(self) -> PtySim:
        for t in self._threads:
            t.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=1.0)
        os.close(self.master)
        os.close(self.slave)

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    def _io(self) -> None:
        while not self._stop.is_set():
            r, _, _ = select.select([self.master], [], [], 0.05)
            if not r:
                continue
            try:
                data = os.read(self.master, 4096)
            except OSError:
                continue
            with self.lock:
                self.serial.write(data)
                out = self.serial.read(self.serial.in_waiting)
            if out:
                os.write(self.master, out)

    def _physics(self) -> None:
        last = time.monotonic()
        while not self._stop.is_set():
            time.sleep(self.physics_dt)
            now = time.monotonic()
            with self.lock:
                self.backend.advance(now - last)
            last = now


def make_backend(kind: str, config: str, policy: str):
    cfg = load_config(config)
    meta = OnnxPolicy(policy).meta
    idx = [meta.joint_names.index(n) for n in cfg.joint_map.names]
    q0 = meta.default_joint_pos[idx]
    if kind == "kinematic":
        return KinematicBackend(cfg.joint_map, q0)
    return MujocoBackend(cfg.joint_map, q0, dict(zip(meta.joint_names, meta.default_joint_pos)))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/xgo_lite_v2.yaml")
    ap.add_argument("--policy", default="policies/latest.onnx", help="source of the default pose")
    ap.add_argument("--sim", choices=["kinematic", "mujoco"], default="mujoco")
    a = ap.parse_args(argv)
    with PtySim(make_backend(a.sim, a.config, a.policy)) as sim:
        print(sim.path, flush=True)
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
