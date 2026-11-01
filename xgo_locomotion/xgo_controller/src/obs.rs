//! Actor observation of luwu_mjlab's flat velocity task (no height scan):
//! [ang_vel(3), projected_gravity(3), command(3), phase(2), joint_pos_rel(n), joint_vel(n), last_action(n)]

/// Unit gravity in the body frame for ZYX (yaw-pitch-roll) Euler angles in rad.
pub fn projected_gravity(roll: f64, pitch: f64) -> [f64; 3] {
    let cp = pitch.cos();
    [pitch.sin(), -cp * roll.sin(), -cp * roll.cos()]
}

pub fn phase(t: f64, period: f64, command: &[f64; 3], stand_threshold: f64) -> [f64; 2] {
    let norm = command.iter().map(|c| c * c).sum::<f64>().sqrt();
    if norm < stand_threshold {
        return [0.0, 0.0];
    }
    let x = t.rem_euclid(period) / period * std::f64::consts::TAU;
    [x.sin(), x.cos()]
}

pub fn build(
    ang_vel: &[f64; 3],
    gravity: &[f64; 3],
    command: &[f64; 3],
    phase: &[f64; 2],
    joint_pos_rel: &[f64],
    joint_vel: &[f64],
    last_action: &[f64],
) -> Vec<f32> {
    ang_vel
        .iter()
        .chain(gravity)
        .chain(command)
        .chain(phase)
        .chain(joint_pos_rel)
        .chain(joint_vel)
        .chain(last_action)
        .map(|&v| v as f32)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gravity_level_and_tilted() {
        assert_eq!(projected_gravity(0.0, 0.0), [0.0, -0.0, -1.0]);
        let g = projected_gravity(0.0, 0.3);
        assert!((g[0] - 0.3f64.sin()).abs() < 1e-12);
    }

    #[test]
    fn phase_zero_when_standing() {
        assert_eq!(phase(0.13, 0.4, &[0.05, 0.0, 0.0], 0.1), [0.0, 0.0]);
        let p = phase(0.1, 0.4, &[0.3, 0.0, 0.0], 0.1);
        assert!((p[0] - 1.0).abs() < 1e-12 && p[1].abs() < 1e-12);
    }
}
