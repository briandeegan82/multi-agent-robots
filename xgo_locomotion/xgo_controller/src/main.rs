//! xgo_controller: run a luwu_mjlab ONNX locomotion policy on an XGO Lite v2 from a Rock Pi 4.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use anyhow::bail;
use clap::{Parser, Subcommand};
use xgo_controller::config::RobotConfig;
use xgo_controller::controller::Controller;
use xgo_controller::driver::{Driver, open_serial};
use xgo_controller::policy::OnnxPolicy;

#[derive(Parser)]
#[command(about)]
struct Cli {
    #[arg(long, default_value = "config/xgo_lite_v2.yaml")]
    config: String,
    /// UART device (Rock Pi 4 UART4 = /dev/ttyS4 with the uart4 overlay)
    #[arg(long, default_value = "/dev/ttyS4")]
    port: String,
    /// Per-read reply timeout in ms
    #[arg(long, default_value_t = 20)]
    read_timeout_ms: u64,
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Stand up, run the policy for --duration s, then firmware reset
    Run {
        #[arg(long)]
        policy: String,
        #[arg(long, default_value_t = 0.0, allow_hyphen_values = true)]
        vx: f64,
        #[arg(long, default_value_t = 0.0, allow_hyphen_values = true)]
        vy: f64,
        #[arg(long, default_value_t = 0.0, allow_hyphen_values = true)]
        wz: f64,
        #[arg(long, default_value_t = 10.0)]
        duration: f64,
        /// CSV log: t, raw u8 (12), gyro dps (3), rpy deg (3), cmd (3), obs, action, target (12)
        #[arg(long)]
        log: Option<String>,
        #[arg(long)]
        allow_uncalibrated: bool,
        #[arg(long)]
        no_stand_up: bool,
    },
    /// Measure read-motors + read-IMU + write-legs cycle time over the link (robot holds pose)
    Bench {
        #[arg(long, default_value_t = 500)]
        cycles: usize,
    },
    /// Print live motor angles (motor deg) and IMU at 5 Hz
    Stream,
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    let cfg = RobotConfig::load(&cli.config)?;
    let port = open_serial(&cli.port, cfg.control.baud)?;
    let mut drv = Driver::new(port, Duration::from_millis(cli.read_timeout_ms));
    println!(
        "firmware: {}  battery: {}",
        drv.read_firmware()?,
        drv.read_battery()?
    );
    let stop = Arc::new(AtomicBool::new(false));
    let s = stop.clone();
    ctrlc::set_handler(move || s.store(true, Ordering::SeqCst))?;

    match cli.cmd {
        Cmd::Run {
            policy,
            vx,
            vy,
            wz,
            duration,
            log,
            allow_uncalibrated,
            no_stand_up,
        } => {
            if !cfg.calibrated && !allow_uncalibrated {
                bail!(
                    "config is not calibrated; run xgo-calibrate first (or --allow-uncalibrated)"
                );
            }
            let policy = OnnxPolicy::load(&policy)?;
            let mut ctl = Controller::new(drv, cfg, &policy)?;
            if let Some(path) = log {
                ctl.log = Some(Box::new(std::io::BufWriter::new(std::fs::File::create(
                    path,
                )?)));
            }
            if !no_stand_up {
                ctl.stand_up()?;
            }
            let res = ctl.run(duration, [vx, vy, wz], stop);
            if let Some(w) = ctl.log.as_mut() {
                w.flush()?;
            }
            let mut c: Vec<f64> = ctl.cycle_s.iter().map(|v| v * 1e3).collect();
            c.sort_by(f64::total_cmp);
            if !c.is_empty() {
                let mean = c.iter().sum::<f64>() / c.len() as f64;
                println!(
                    "steps {}  cycle ms mean {mean:.2}  p95 {:.2}  max {:.2}",
                    c.len(),
                    c[c.len() * 95 / 100],
                    c[c.len() - 1]
                );
            }
            res
        }
        Cmd::Bench { cycles } => {
            let n = cfg.joint_map.first_register() + cfg.joint_map.len();
            let hold = drv.read_motors(n)?;
            let mut t = Vec::new();
            let mut timeouts = 0;
            for _ in 0..cycles {
                if stop.load(Ordering::SeqCst) {
                    break;
                }
                let s = Instant::now();
                let ok = drv.read_motors(15).is_ok()
                    && if cfg.imu.source == "imu65" {
                        drv.read_imu().is_ok()
                    } else {
                        drv.read_rpy().is_ok()
                    };
                if !ok {
                    timeouts += 1;
                    continue;
                }
                drv.write_motors(
                    cfg.joint_map.first_register(),
                    &hold[cfg.joint_map.first_register()..],
                )?;
                t.push(s.elapsed().as_secs_f64() * 1e3);
            }
            if t.is_empty() {
                bail!("all reads timed out");
            }
            t.sort_by(f64::total_cmp);
            let p95 = t[t.len() * 95 / 100];
            let hz = 1e3 / p95;
            println!(
                "cycles {}/{cycles} timeouts {timeouts} bytes/cycle {:.0}",
                t.len(),
                (drv.bytes_tx + drv.bytes_rx) as f64 / cycles as f64
            );
            println!(
                "cycle ms: mean {:.2} p50 {:.2} p95 {p95:.2} max {:.2} -> ~{hz:.0} Hz ({} for {} Hz)",
                t.iter().sum::<f64>() / t.len() as f64,
                t[t.len() / 2],
                t[t.len() - 1],
                if hz > cfg.control.control_hz * 1.25 {
                    "OK"
                } else {
                    "TOO SLOW"
                },
                cfg.control.control_hz
            );
            Ok(())
        }
        Cmd::Stream => {
            let n = cfg.joint_map.first_register() + cfg.joint_map.len();
            while !stop.load(Ordering::SeqCst) {
                let raw = drv.read_motors(n)?;
                let deg = cfg
                    .joint_map
                    .motor_deg_from_u8(&raw[cfg.joint_map.first_register()..]);
                let imu = drv.read_imu()?;
                let names = cfg.joint_map.names();
                let s: Vec<String> = names
                    .iter()
                    .zip(&deg)
                    .map(|(n, d)| format!("{}={d:6.1}", n.trim_end_matches("_joint")))
                    .collect();
                println!(
                    "{}\n   rpy_deg={:.1?} gyro_dps={:.1?}",
                    s.join(" "),
                    imu.rpy_deg,
                    imu.gyro_dps
                );
                std::thread::sleep(Duration::from_millis(200));
            }
            Ok(())
        }
    }
}
