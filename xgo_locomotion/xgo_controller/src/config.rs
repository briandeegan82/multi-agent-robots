//! Same YAML file as the Python runtime (`config/xgo_lite_v2.yaml`).

use std::path::Path;

use serde::Deserialize;

use crate::joint_map::{JointMap, JointSpec};

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct ImuConfig {
    pub source: String,
    pub gyro_axes: [usize; 3],
    pub gyro_sign: [f64; 3],
    pub roll_sign: f64,
    pub pitch_sign: f64,
}

impl Default for ImuConfig {
    fn default() -> Self {
        Self {
            source: "imu65".into(),
            gyro_axes: [0, 1, 2],
            gyro_sign: [1.0; 3],
            roll_sign: 1.0,
            pitch_sign: 1.0,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct SafetyConfig {
    pub tilt_limit_deg: f64,
    pub joint_margin_deg: f64,
    pub max_step_rad: f64,
    pub max_read_failures: usize,
    pub on_fault: String,
}

impl Default for SafetyConfig {
    fn default() -> Self {
        Self {
            tilt_limit_deg: 35.0,
            joint_margin_deg: 2.0,
            max_step_rad: 0.15,
            max_read_failures: 3,
            on_fault: "reset".into(),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct ControlConfig {
    pub control_hz: f64,
    pub phase_period: f64,
    pub stand_threshold: f64,
    pub stand_up_s: f64,
    pub joint_vel_ema: f64,
    pub baud: u32,
}

impl Default for ControlConfig {
    fn default() -> Self {
        Self {
            control_hz: 50.0,
            phase_period: 0.4,
            stand_threshold: 0.1,
            stand_up_s: 2.0,
            joint_vel_ema: 1.0,
            baud: 115_200,
        }
    }
}

#[derive(Debug, Deserialize)]
struct RawConfig {
    #[serde(default)]
    calibrated: bool,
    joints: Vec<JointSpec>,
    #[serde(default)]
    imu: ImuConfig,
    #[serde(default)]
    safety: SafetyConfig,
    #[serde(default)]
    control: ControlConfig,
}

#[derive(Debug, Clone)]
pub struct RobotConfig {
    pub calibrated: bool,
    pub joint_map: JointMap,
    pub imu: ImuConfig,
    pub safety: SafetyConfig,
    pub control: ControlConfig,
}

impl RobotConfig {
    pub fn load(path: impl AsRef<Path>) -> anyhow::Result<Self> {
        let raw: RawConfig = serde_yaml::from_str(&std::fs::read_to_string(path)?)?;
        anyhow::ensure!(
            matches!(raw.imu.source.as_str(), "imu65" | "rpy62"),
            "imu.source must be imu65 or rpy62"
        );
        anyhow::ensure!(
            matches!(raw.safety.on_fault.as_str(), "reset" | "unload" | "hold"),
            "safety.on_fault must be reset, unload or hold"
        );
        Ok(Self {
            calibrated: raw.calibrated,
            joint_map: JointMap::new(raw.joints)?,
            imu: raw.imu,
            safety: raw.safety,
            control: raw.control,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn loads_repo_config() {
        let cfg = RobotConfig::load(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../config/xgo_lite_v2.yaml"
        ))
        .unwrap();
        assert_eq!(cfg.joint_map.len(), 12);
        assert!(!cfg.calibrated);
        assert_eq!(cfg.control.control_hz, 50.0);
    }
}
