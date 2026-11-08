//! Policy joint angle (rad, sim convention) <-> XGO servo register (u8).
//! motor_deg = sign * deg(q) + offset_deg; u8 spans xgolib's xgolite MOTOR_LIMIT per role.

use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct JointSpec {
    pub name: String,
    pub register: usize,
    pub role: String,
    pub sign: f64,
    pub offset_deg: f64,
}

pub fn role_limits_deg(role: &str) -> anyhow::Result<(f64, f64)> {
    Ok(match role {
        "lower" => (-70.0, 50.0),
        "mid" => (-70.0, 90.0),
        "upper" => (-30.0, 30.0),
        _ => anyhow::bail!("unknown servo role {role}"),
    })
}

#[derive(Debug, Clone)]
pub struct JointMap {
    pub joints: Vec<JointSpec>,
    lo: Vec<f64>,
    hi: Vec<f64>,
}

impl JointMap {
    pub fn new(joints: Vec<JointSpec>) -> anyhow::Result<Self> {
        let mut lo = Vec::new();
        let mut hi = Vec::new();
        for (i, j) in joints.iter().enumerate() {
            let (l, h) = role_limits_deg(&j.role)?;
            lo.push(l);
            hi.push(h);
            anyhow::ensure!(
                j.sign == 1.0 || j.sign == -1.0,
                "sign of {} must be +-1",
                j.name
            );
            anyhow::ensure!(
                j.register == joints[0].register + i,
                "registers must be contiguous and increasing"
            );
        }
        Ok(Self { joints, lo, hi })
    }

    pub fn len(&self) -> usize {
        self.joints.len()
    }

    pub fn is_empty(&self) -> bool {
        self.joints.is_empty()
    }

    pub fn first_register(&self) -> usize {
        self.joints[0].register
    }

    pub fn names(&self) -> Vec<&str> {
        self.joints.iter().map(|j| j.name.as_str()).collect()
    }

    pub fn to_u8(&self, q: &[f64]) -> Vec<u8> {
        self.joints
            .iter()
            .enumerate()
            .map(|(i, j)| {
                let deg = (j.sign * q[i].to_degrees() + j.offset_deg).clamp(self.lo[i], self.hi[i]);
                ((deg - self.lo[i]) / (self.hi[i] - self.lo[i]) * 255.0).round_ties_even() as u8
            })
            .collect()
    }

    pub fn from_u8(&self, u: &[u8]) -> Vec<f64> {
        self.joints
            .iter()
            .enumerate()
            .map(|(i, j)| {
                let deg = u[i] as f64 / 255.0 * (self.hi[i] - self.lo[i]) + self.lo[i];
                ((deg - j.offset_deg) / j.sign).to_radians()
            })
            .collect()
    }

    pub fn motor_deg_from_u8(&self, u: &[u8]) -> Vec<f64> {
        (0..self.len())
            .map(|i| u[i] as f64 / 255.0 * (self.hi[i] - self.lo[i]) + self.lo[i])
            .collect()
    }

    /// Motor limits as sim joint angles (rad), (lo, hi) per joint.
    pub fn sim_limits(&self) -> (Vec<f64>, Vec<f64>) {
        let a = self.from_u8(&vec![0u8; self.len()]);
        let b = self.from_u8(&vec![255u8; self.len()]);
        (
            a.iter().zip(&b).map(|(x, y)| x.min(*y)).collect(),
            a.iter().zip(&b).map(|(x, y)| x.max(*y)).collect(),
        )
    }

    pub fn quantum_rad(&self) -> Vec<f64> {
        (0..self.len())
            .map(|i| ((self.hi[i] - self.lo[i]) / 255.0).to_radians())
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn spec(name: &str, register: usize, role: &str, sign: f64, offset_deg: f64) -> JointSpec {
        JointSpec {
            name: name.into(),
            register,
            role: role.into(),
            sign,
            offset_deg,
        }
    }

    #[test]
    fn roundtrip_within_half_count() {
        let jm = JointMap::new(vec![
            spec("a", 0, "lower", -1.0, 10.0),
            spec("b", 1, "mid", 1.0, -20.0),
            spec("c", 2, "upper", 1.0, 0.0),
        ])
        .unwrap();
        let (lo, hi) = jm.sim_limits();
        let qm = jm.quantum_rad();
        for k in 0..=100 {
            let q: Vec<f64> = (0..3)
                .map(|i| lo[i] + (hi[i] - lo[i]) * k as f64 / 100.0)
                .collect();
            let back = jm.from_u8(&jm.to_u8(&q));
            for i in 0..3 {
                assert!((back[i] - q[i]).abs() <= qm[i] / 2.0 + 1e-9);
            }
        }
    }

    #[test]
    fn rejects_gaps() {
        assert!(
            JointMap::new(vec![
                spec("a", 0, "lower", 1.0, 0.0),
                spec("b", 2, "mid", 1.0, 0.0)
            ])
            .is_err()
        );
    }
}
