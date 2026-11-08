//! Policy loop: read XGO state -> observation -> ONNX -> clamped servo targets.

use std::io::Write;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use anyhow::{bail, ensure};

use crate::config::RobotConfig;
use crate::driver::{Driver, Port, Timeout};
use crate::obs;
use crate::policy::OnnxPolicy;

pub struct Controller<'a, P: Port> {
    pub drv: Driver<P>,
    pub cfg: RobotConfig,
    policy: &'a OnnxPolicy,
    pol_idx: Vec<usize>,
    default: Vec<f64>,
    q_lo: Vec<f64>,
    q_hi: Vec<f64>,
    last_action: Vec<f64>,
    q_full: Vec<f64>,
    dq_full: Vec<f64>,
    prev: Option<(f64, Vec<f64>, [f64; 3])>,
    target: Option<Vec<f64>>,
    read_failures: usize,
    pub log: Option<Box<dyn Write>>,
    pub cycle_s: Vec<f64>,
}

pub struct State {
    pub raw: Vec<u8>,
    pub gyro_dps: [f64; 3],
    pub rpy_deg: [f64; 3],
}

impl<'a, P: Port> Controller<'a, P> {
    pub fn new(drv: Driver<P>, cfg: RobotConfig, policy: &'a OnnxPolicy) -> anyhow::Result<Self> {
        let meta = &policy.meta;
        let jm = &cfg.joint_map;
        let mut pol_idx = Vec::new();
        for n in jm.names() {
            match meta.joint_names.iter().position(|m| m == n) {
                Some(i) => pol_idx.push(i),
                None => bail!("config joint {n} not in policy"),
            }
        }
        let (lo, hi) = jm.sim_limits();
        let m = cfg.safety.joint_margin_deg.to_radians();
        let n = meta.joint_names.len();
        Ok(Self {
            q_lo: lo.iter().map(|v| v + m).collect(),
            q_hi: hi.iter().map(|v| v - m).collect(),
            default: meta.default_joint_pos.clone(),
            last_action: vec![0.0; n],
            q_full: meta.default_joint_pos.clone(),
            dq_full: vec![0.0; n],
            prev: None,
            target: None,
            read_failures: 0,
            log: None,
            cycle_s: Vec::new(),
            drv,
            cfg,
            policy,
            pol_idx,
        })
    }

    fn n_regs(&self) -> usize {
        self.cfg.joint_map.first_register() + self.cfg.joint_map.len()
    }

    pub fn read_state(&mut self) -> anyhow::Result<State> {
        let first = self.cfg.joint_map.first_register();
        let raw = self.drv.read_motors(self.n_regs())?[first..].to_vec();
        let (gyro_dps, rpy_deg) = if self.cfg.imu.source == "imu65" {
            let s = self.drv.read_imu()?;
            (s.gyro_dps, s.rpy_deg)
        } else {
            ([f64::NAN; 3], self.drv.read_rpy()?)
        };
        Ok(State {
            raw,
            gyro_dps,
            rpy_deg,
        })
    }

    pub fn write_targets(&mut self, q: &[f64]) -> anyhow::Result<Vec<f64>> {
        let mut q: Vec<f64> = q
            .iter()
            .enumerate()
            .map(|(i, v)| v.clamp(self.q_lo[i], self.q_hi[i]))
            .collect();
        if let Some(prev) = &self.target {
            let m = self.cfg.safety.max_step_rad;
            for (v, p) in q.iter_mut().zip(prev) {
                *v = v.clamp(p - m, p + m);
            }
        }
        let u8s = self.cfg.joint_map.to_u8(&q);
        self.drv
            .write_motors(self.cfg.joint_map.first_register(), &u8s)?;
        self.target = Some(q.clone());
        Ok(q)
    }

    /// One control step at time `t` (s since start) with velocity command `cmd`.
    pub fn step(&mut self, t: f64, cmd: [f64; 3]) -> anyhow::Result<()> {
        let st = match self.read_state() {
            Ok(s) => {
                self.read_failures = 0;
                s
            }
            Err(e) if e.is::<Timeout>() => {
                self.read_failures += 1;
                ensure!(
                    self.read_failures < self.cfg.safety.max_read_failures,
                    "FAULT: too many consecutive read timeouts"
                );
                return Ok(());
            }
            Err(e) => return Err(e),
        };
        let imu = &self.cfg.imu;
        let rpy = st.rpy_deg.map(f64::to_radians);
        let (roll, pitch) = (rpy[0] * imu.roll_sign, rpy[1] * imu.pitch_sign);
        let lim = self.cfg.safety.tilt_limit_deg;
        ensure!(
            roll.to_degrees().abs() <= lim && pitch.to_degrees().abs() <= lim,
            "FAULT: tilt roll {:.1} pitch {:.1} deg exceeds {lim}",
            roll.to_degrees(),
            pitch.to_degrees()
        );
        let q = self.cfg.joint_map.from_u8(&st.raw);
        let dt = self
            .prev
            .as_ref()
            .map_or(1.0 / self.cfg.control.control_hz, |p| (t - p.0).max(1e-3));
        let ang_vel: [f64; 3] = if imu.source == "imu65" {
            [0, 1, 2].map(|i| st.gyro_dps[imu.gyro_axes[i]].to_radians() * imu.gyro_sign[i])
        } else {
            self.prev
                .as_ref()
                .map_or([0.0; 3], |p| [0, 1, 2].map(|i| (rpy[i] - p.2[i]) / dt))
        };
        let a = self.cfg.control.joint_vel_ema;
        for (k, &pi) in self.pol_idx.iter().enumerate() {
            let dq = self.prev.as_ref().map_or(0.0, |p| (q[k] - p.1[k]) / dt);
            self.dq_full[pi] = a * dq + (1.0 - a) * self.dq_full[pi];
            self.q_full[pi] = q[k];
        }
        self.prev = Some((t, q.clone(), rpy));
        let c = &self.cfg.control;
        let q_rel: Vec<f64> = self
            .q_full
            .iter()
            .zip(&self.default)
            .map(|(q, d)| q - d)
            .collect();
        let o = obs::build(
            &ang_vel,
            &obs::projected_gravity(roll, pitch),
            &cmd,
            &obs::phase(t, c.phase_period, &cmd, c.stand_threshold),
            &q_rel,
            &self.dq_full,
            &self.last_action,
        );
        let action = self.policy.act(&o)?;
        let scale = self.policy.meta.action_scale;
        let tgt: Vec<f64> = self
            .pol_idx
            .iter()
            .map(|&i| self.default[i] + scale * action[i])
            .collect();
        let sent = self.write_targets(&tgt)?;
        self.last_action = action.clone();
        if let Some(w) = self.log.as_mut() {
            let mut row = vec![t];
            row.extend(st.raw.iter().map(|&v| v as f64));
            row.extend(st.gyro_dps);
            row.extend(st.rpy_deg);
            row.extend(cmd);
            row.extend(o.iter().map(|&v| v as f64));
            row.extend(&action);
            row.extend(&sent);
            let s: Vec<String> = row.iter().map(|v| format!("{v:.9e}")).collect();
            writeln!(w, "{}", s.join(","))?;
        }
        Ok(())
    }

    /// Ramp from the measured pose to the policy default pose.
    pub fn stand_up(&mut self) -> anyhow::Result<()> {
        let first = self.cfg.joint_map.first_register();
        let raw = self.drv.read_motors(self.n_regs())?[first..].to_vec();
        let q0 = self.cfg.joint_map.from_u8(&raw);
        let q1: Vec<f64> = self
            .pol_idx
            .iter()
            .enumerate()
            .map(|(k, &i)| self.default[i].clamp(self.q_lo[k], self.q_hi[k]))
            .collect();
        let dt = 1.0 / self.cfg.control.control_hz;
        let n = ((self.cfg.control.stand_up_s / dt) as usize).max(1);
        for s in 1..=n {
            self.target = None;
            let f = s as f64 / n as f64;
            let q: Vec<f64> = q0.iter().zip(&q1).map(|(a, b)| a + (b - a) * f).collect();
            self.write_targets(&q)?;
            std::thread::sleep(Duration::from_secs_f64(dt));
        }
        Ok(())
    }

    pub fn safe_stop(&mut self) -> anyhow::Result<()> {
        match self.cfg.safety.on_fault.as_str() {
            "reset" => self.drv.reset(),
            "unload" => self.drv.unload_all(),
            _ => Ok(()),
        }
    }

    /// Fixed-rate loop; always ends with `safe_stop` (also on fault or Ctrl-C).
    pub fn run(
        &mut self,
        duration: f64,
        cmd: [f64; 3],
        stop: Arc<AtomicBool>,
    ) -> anyhow::Result<()> {
        let dt = Duration::from_secs_f64(1.0 / self.cfg.control.control_hz);
        let t0 = Instant::now();
        let mut next = t0;
        let res = (|| {
            while t0.elapsed().as_secs_f64() < duration && !stop.load(Ordering::SeqCst) {
                let start = Instant::now();
                self.step((start - t0).as_secs_f64(), cmd)?;
                self.cycle_s.push(start.elapsed().as_secs_f64());
                next += dt;
                let now = Instant::now();
                if next > now {
                    std::thread::sleep(next - now);
                } else {
                    next = now;
                }
            }
            Ok(())
        })();
        let stop_res = self.safe_stop();
        res.and(stop_res)
    }
}
