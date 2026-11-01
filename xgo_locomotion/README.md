# xgo_locomotion: learned locomotion for XGO Lite v2 on a Rock Pi 4

Train a velocity-tracking walking policy in simulation, export it to ONNX, and run it on a Rock Pi 4 that
drives an XGO Lite v2 over its UART.

```
luwu_mjlab (MuJoCo-Warp + RSL-RL PPO)  ->  policy.onnx  ->  xgo_controller (Rust, Rock Pi 4)  ->  XGO UART
     train/  (GPU box)                     policies/         xgo_controller/                       115200 8N1
```

**Starting point.** Luwu Dynamics (who make the XGO) publish [luwu_mjlab](https://github.com/LuwuDynamics/luwu_mjlab).
It has no Lite v2 model, so this project trains their default `Lite3-Walk-Flat` task unchanged: a 512-256-128 ELU
actor-critic with the default PPO settings, a 50 Hz flat-ground velocity-tracking task, and actions as joint-position
offsets (`q = default + 0.25 * a`). The Lite3 has the same 3-DOF-per-leg layout plus a 2-DOF arm. The controller
holds the arm joints at their default pose in the observation. **The Lite3 geometry, mass and servo model stand in
for the Lite v2 until we have a Lite v2 MJCF.** Do not expect this policy to walk well on the real robot yet.

| Part | What |
|---|---|
| `train/` | Pinned luwu_mjlab setup (`setup_train_env.sh`), `train.sh` (full or `SMOKE=1` CPU run), `export_policy.sh` → `policies/latest.onnx` |
| `xgo_controller/` | **Rock Pi runtime (Rust)**: XGO protocol + driver, observation builder, ONNX inference (`tract`, pure Rust), fixed-rate loop, safety. Subcommands `run`, `bench`, `stream` |
| `xgo_rl/` | Python reference implementation of the same runtime, plus the simulated XGO (`sim_xgo.py`, `pty_sim.py`) and the calibration tool `xgo-calibrate` |
| `config/xgo_lite_v2.yaml` | Joint ↔ servo-register map (sign, zero offset, servo role), IMU signs, safety limits, rate. Shared by Rust and Python |
| `tests/` | Protocol, mapping, observation, closed-loop and Rust-vs-Python parity tests |

## 1. Train (GPU machine, e.g. GB10)

```bash
train/setup_train_env.sh ~/venvs/mjlab        # clones luwu_mjlab at a pinned commit, installs pinned deps
source ~/venvs/mjlab/bin/activate
train/train.sh Lite3-Walk-Flat                # 4096 envs, 1500 iterations, then exports policies/latest.onnx
SMOKE=1 train/train.sh                        # CPU plumbing check: 64 envs, 3 iterations (~1 min + Warp compile)
```

The export embeds the contract in the ONNX metadata: joint order, default pose, action scale, and observation terms.
Both runtimes check it on load. Actor observation (53 values): `ang_vel(3) projected_gravity(3) command(3)
phase(2) joint_pos-default(14) joint_vel(14) last_action(14)`. `phase` is `[sin, cos]` of a 0.4 s clock and is zeroed
when `|command| < 0.1`.

## 2. Test without the robot

```bash
pip install -e '.[dev,sim]'
cargo build --release --manifest-path xgo_controller/Cargo.toml
LUWU_MJLAB_DIR=train/luwu_mjlab pytest -q                 # MuJoCo tests need the luwu clone (Lite3 MJCF)
XGO_MJLAB_PARITY=1 LUWU_MJLAB_DIR=... pytest tests/test_mjlab_parity.py   # our obs == luwu_mjlab's actor obs
```

The simulated XGO speaks the real byte protocol behind a pseudo-terminal, so the unmodified Rust binary runs against it:

```bash
xgo-sim-serve --sim mujoco --policy policies/latest.onnx     # prints /dev/pts/N
xgo_controller/target/release/xgo_controller --port /dev/pts/N run --policy policies/latest.onnx --vx 0.2 --allow-uncalibrated
```

`tests/test_rust_controller.py` runs this loop with kinematic and MuJoCo backends. It checks that every Rust
observation and action matches the Python reference (atol 1e-5). The Python observation builder is in turn checked
against luwu_mjlab's own `actor` observation by `test_mjlab_parity.py`.

## 3. Rock Pi 4

**Build.** Cross-compile on any x86 Linux box, then copy the binary and policy over:

```bash
sudo apt install gcc-aarch64-linux-gnu && rustup target add aarch64-unknown-linux-gnu
cargo build --release --target aarch64-unknown-linux-gnu --manifest-path xgo_controller/Cargo.toml
scp xgo_controller/target/aarch64-unknown-linux-gnu/release/xgo_controller config/xgo_lite_v2.yaml policies/latest.onnx rock@rockpi:xgo/
```

The binary needs glibc ≥ 2.34 (Debian 12 / Ubuntu 22.04 or newer Rock Pi images). It has no onnxruntime dependency.

**Wiring.** Connect a Rock Pi UART to the XGO's serial header: TX→RX, RX→TX, common GND. Both sides should be
3.3 V TTL; **check the XGO header voltage before connecting**. UART2 (pins 8/10, `/dev/ttyS2`) is the Rock Pi debug
console by default, so use UART4 (`/dev/ttyS4`, the `--port` default). Enable its device-tree overlay, check the
pins against Radxa's Rock Pi 4 GPIO docs, and add your user to `dialout`.

**Bring-up order** (robot on a stand, legs free, battery charged):

1. `xgo_controller --port /dev/ttyS4 stream`: firmware/battery print; angles and IMU change as you move legs and the body.
2. `xgo_controller --port /dev/ttyS4 bench`: read+write cycle time. You need p95 < 16 ms for 50 Hz (it prints OK / TOO
   SLOW). If it's too slow: drop `imu.source` to `rpy62` (fewer bytes), else retrain with `decimation` 10 (25 Hz).
3. Calibrate (Python tool, runs on the Pi or a laptop with a USB-UART):
   `pip install -e .` then `xgo-calibrate --port /dev/ttyS4 sign` (jogs each joint and asks which way the foot moved),
   `... offset` (firmware stand pose vs policy default pose), `... imu` (tilt nose-down / right-side-down).
   It writes a config with `calibrated: true` only after every joint has been sign-checked.
4. `xgo_controller --config config/xgo_lite_v2.calibrated.yaml run --policy latest.onnx --duration 5`
   (zero command, stand in place), then small `--vx 0.1`, with a hand ready to catch the robot.

**Safety.** `run` refuses an uncalibrated config unless you pass `--allow-uncalibrated`. Each target is clamped to the
xgolib servo limits minus `joint_margin_deg` and rate-limited to `max_step_rad` per step. Roll or pitch beyond
`tilt_limit_deg`, `max_read_failures` consecutive read timeouts, or Ctrl-C all end in `safety.on_fault`
(`reset` = firmware stand pose, `unload` = servos limp, `hold`).

## Known gaps

- No Lite v2 model: the next step is a Lite v2 MJCF (link lengths, masses, servo kp/limits from the robot), then retraining.
- Sign/offset calibration and UART timing have not been measured on hardware yet. Every config value marked
  `placeholder` is a guess.
- The firmware's servo-position registers are 8-bit (≈0.5–0.8° per count), and joint velocity is a finite difference
  of those readings. Expect noisy `joint_vel` observations; retrain with matching noise/quantisation if the policy
  reacts badly to it.
