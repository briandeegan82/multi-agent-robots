#!/usr/bin/env bash
# Copy the newest policy.onnx written by VelocityOnPolicyRunner (on every checkpoint save)
# into policies/<experiment>_<run>.onnx and policies/latest.onnx, then validate it.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(ls -t "$HERE"/luwu_mjlab/logs/rsl_rl/*/*/policy.onnx | head -1)"
RUN="$(basename "$(dirname "$SRC")")"
EXP="$(basename "$(dirname "$(dirname "$SRC")")")"
mkdir -p "$HERE/../policies"
cp "$SRC" "$HERE/../policies/${EXP}_${RUN}.onnx"
cp "$SRC" "$HERE/../policies/latest.onnx"
python -c "from xgo_rl.policy import OnnxPolicy; import sys; m = OnnxPolicy(sys.argv[1]).meta; \
print('ok', m.obs_dim, 'obs ->', m.act_dim, 'actions', m.joint_names)" "$HERE/../policies/latest.onnx"
