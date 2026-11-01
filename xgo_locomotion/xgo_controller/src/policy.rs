//! ONNX policy via tract; the contract comes from the luwu_mjlab export metadata.

use std::collections::HashMap;

use anyhow::{Context, bail, ensure};
use tract_onnx::prelude::*;

pub const EXPECTED_OBS: [&str; 7] = [
    "base_ang_vel",
    "projected_gravity",
    "command",
    "phase",
    "joint_pos",
    "joint_vel",
    "actions",
];

#[derive(Debug, Clone)]
pub struct PolicyMeta {
    pub joint_names: Vec<String>,
    pub default_joint_pos: Vec<f64>,
    pub action_scale: f64,
    pub obs_dim: usize,
}

fn csv(s: &str) -> Vec<String> {
    s.split(',')
        .filter(|v| !v.is_empty())
        .map(str::to_string)
        .collect()
}

pub fn parse_meta(props: &HashMap<String, String>) -> anyhow::Result<PolicyMeta> {
    let get = |k: &str| {
        props
            .get(k)
            .with_context(|| format!("ONNX metadata missing {k}"))
    };
    let obs = csv(get("observation_names")?);
    if obs != EXPECTED_OBS {
        bail!("unsupported observation terms {obs:?}");
    }
    let joint_names = csv(get("joint_names")?);
    let default_joint_pos = csv(get("default_joint_pos")?)
        .iter()
        .map(|v| v.parse())
        .collect::<Result<Vec<f64>, _>>()?;
    ensure!(
        default_joint_pos.len() == joint_names.len(),
        "default_joint_pos length mismatch"
    );
    Ok(PolicyMeta {
        obs_dim: 11 + 3 * joint_names.len(),
        joint_names,
        default_joint_pos,
        action_scale: get("action_scale")?.parse()?,
    })
}

pub struct OnnxPolicy {
    pub meta: PolicyMeta,
    model: Arc<TypedRunnableModel>,
}

impl OnnxPolicy {
    pub fn load(path: &str) -> anyhow::Result<Self> {
        let onnx = tract_onnx::onnx();
        let proto = onnx.proto_model_for_path(path)?;
        let props: HashMap<String, String> = proto
            .metadata_props
            .iter()
            .map(|p| (p.key.clone(), p.value.clone()))
            .collect();
        let meta = parse_meta(&props)?;
        let model = onnx
            .model_for_proto_model(&proto)?
            .with_input_fact(0, f32::fact([1, meta.obs_dim]).into())?
            .into_optimized()?
            .into_runnable()?;
        Ok(Self { meta, model })
    }

    pub fn act(&self, obs: &[f32]) -> anyhow::Result<Vec<f64>> {
        ensure!(
            obs.len() == self.meta.obs_dim,
            "obs has {} values",
            obs.len()
        );
        let input = Tensor::from_shape(&[1, obs.len()], obs)?;
        let out = self.model.run(tvec!(input.into()))?;
        let a = out[0].to_plain_array_view::<f32>()?;
        let a: Vec<f64> = a.iter().map(|&v| v as f64).collect();
        ensure!(
            a.len() == self.meta.joint_names.len(),
            "policy returned {} actions",
            a.len()
        );
        Ok(a)
    }
}
