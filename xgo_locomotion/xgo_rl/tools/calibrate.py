"""xgo-calibrate: measure per-joint sign and zero offset between policy joints and XGO servos.

  stream   print live motor angles (deg) and IMU; --unload lets you move the legs by hand
  sign     jog one joint (or all) and answer whether the foot moved the way the sim says
  offset   align the firmware stand pose with the policy default pose
  imu      check roll/pitch/gyro signs against the sim convention while you tilt the robot

Results are written to --out (default: <config>.calibrated.yaml); `calibrated: true` is set once
every joint's sign has been checked and offsets were measured.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import yaml

from ..cli import add_port_args, open_port
from ..config import load_config
from ..driver import XgoDriver

# Foot motion in the Lite3 sim for +0.1 rad at the default pose (body frame: x fwd, y left,
# z up), from MuJoCo forward kinematics of luwu_mjlab lite3.xml.
SIM_FOOT_DIRECTION = {
    "hip": "towards the robot's RIGHT side (and slightly up/down)",
    "thigh": "BACKWARDS and up",
    "shank": "FORWARDS and up (knee folds)",
}
DEFAULT_POLICY_POSE = {"hip": 0.0, "thigh": 0.95, "shank": 0.0}


def joint_kind(name: str) -> str:
    return name.split("_")[1]


def ask(prompt: str) -> bool:
    while True:
        a = input(prompt + " [y/n] ").strip().lower()
        if a in ("y", "n"):
            return a == "y"


def motor_deg(drv: XgoDriver, jm) -> np.ndarray:
    raw = drv.read_motors_u8()[jm.registers]
    return raw.astype(float) / 255.0 * (jm.hi - jm.lo) + jm.lo


def write_motor_deg(drv: XgoDriver, jm, deg: np.ndarray) -> None:
    u8 = np.rint((np.clip(deg, jm.lo, jm.hi) - jm.lo) / (jm.hi - jm.lo) * 255).astype(np.uint8)
    drv.write_motors_u8(int(jm.registers[0]), u8)


def cmd_stream(drv, cfg, args) -> None:
    if args.unload:
        drv.unload_all()
    names = cfg.joint_map.names
    try:
        while True:
            deg = motor_deg(drv, cfg.joint_map)
            s = drv.read_imu()
            print(" ".join(f"{n.split('_joint')[0]}={d:6.1f}" for n, d in zip(names, deg)))
            print(f"   rpy_deg={np.round(s.rpy_deg, 1)} gyro_dps={np.round(s.gyro_dps, 1)}")
            time.sleep(0.2)
    except KeyboardInterrupt:
        if args.unload:
            drv.load_all()


def cmd_sign(drv, cfg, args, out: dict) -> None:
    jm = cfg.joint_map
    names = jm.names if args.joint == "all" else [args.joint]
    print("Hold the robot in the air (feet free) before continuing.")
    for name in names:
        i = jm.names.index(name)
        base = motor_deg(drv, jm)
        jog = base.copy()
        jog[i] += args.deg
        print(f"\n{name}: jogging motor +{args.deg} deg")
        for _ in range(3):
            write_motor_deg(drv, jm, jog)
            time.sleep(0.6)
            write_motor_deg(drv, jm, base)
            time.sleep(0.6)
        same = ask(f"Did the foot move {SIM_FOOT_DIRECTION[joint_kind(name)]} on the +jog?")
        entry = next(j for j in out["joints"] if j["name"] == name)
        entry["sign"] = 1.0 if same else -1.0
        checked = set(out.setdefault("sign_checked", []))
        checked.add(name)
        out["sign_checked"] = sorted(checked)
        print(f"  sign = {entry['sign']:+.0f}")


def cmd_offset(drv, cfg, args, out: dict) -> None:
    print("Sending firmware reset (stand pose); robot must be on the ground.")
    drv.reset()
    time.sleep(args.settle)
    deg = motor_deg(drv, cfg.joint_map)
    for j, d in zip(out["joints"], deg):
        q = np.rad2deg(DEFAULT_POLICY_POSE[joint_kind(j["name"])])
        j["offset_deg"] = round(float(d - j["sign"] * q), 2)
        print(f"  {j['name']:16s} stand {d:6.1f} deg -> offset {j['offset_deg']:6.1f}")
    out["offset_from"] = "firmware_stand"


def cmd_imu(drv, cfg, args, out: dict) -> None:
    def rp() -> np.ndarray:
        return np.array(drv.read_imu().rpy_deg[:2])

    input("Place the robot level, then press Enter")
    r0 = rp()
    input("Lift the robot's LEFT side ~20 deg (roll right, sim roll < 0), then press Enter")
    roll = rp()[0] - r0[0]
    input("Lift the robot's NOSE ~20 deg (sim pitch < 0), then press Enter")
    pitch = rp()[1] - r0[1]
    out.setdefault("imu", {})
    out["imu"]["roll_sign"] = -1.0 if roll > 0 else 1.0
    out["imu"]["pitch_sign"] = -1.0 if pitch > 0 else 1.0
    print(f"measured d_roll={roll:.1f} d_pitch={pitch:.1f} -> {out['imu']}")
    print("Gyro axes/signs: run `stream` and rotate about each axis; edit imu.gyro_* if needed.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    add_port_args(p)
    p.add_argument("--out", help="output yaml (default <config>.calibrated.yaml)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stream")
    s.add_argument("--unload", action="store_true")
    s = sub.add_parser("sign")
    s.add_argument("--joint", default="all")
    s.add_argument("--deg", type=float, default=8.0)
    s = sub.add_parser("offset")
    s.add_argument("--settle", type=float, default=2.0)
    sub.add_parser("imu")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    out_path = Path(args.out or str(Path(args.config).with_suffix("")) + ".calibrated.yaml")
    src = out_path if out_path.exists() else Path(args.config)
    out = yaml.safe_load(src.read_text())
    drv = XgoDriver(open_port(args, cfg), read_timeout=0.2)
    print("firmware:", drv.read_firmware(), " battery:", drv.read_battery())
    if args.cmd == "stream":
        cmd_stream(drv, cfg, args)
        return 0
    {"sign": cmd_sign, "offset": cmd_offset, "imu": cmd_imu}[args.cmd](drv, cfg, args, out)
    names = {j["name"] for j in out["joints"]}
    out["calibrated"] = bool(
        set(out.get("sign_checked", [])) >= names and out.get("offset_from")
    )
    out_path.write_text(yaml.safe_dump(out, sort_keys=False))
    print(f"wrote {out_path} (calibrated: {out['calibrated']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
