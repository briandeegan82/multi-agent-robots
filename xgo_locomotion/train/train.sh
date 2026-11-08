#!/usr/bin/env bash
# Train the default luwu_mjlab policy and copy the exported ONNX into policies/.
# Usage: train/train.sh [TASK] [extra train.py args...]
#   GPU (default model): train/train.sh Lite3-Walk-Flat
#   CPU smoke test:      SMOKE=1 train/train.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK="${1:-Lite3-Walk-Flat}"
shift || true
cd "$HERE/luwu_mjlab"
if [ "${SMOKE:-0}" = "1" ]; then
  export CUDA_VISIBLE_DEVICES=""
  ARGS=(--env.scene.num-envs 64 --agent.max-iterations 3 --agent.logger tensorboard)
else
  ARGS=(--env.scene.num-envs 4096 --agent.logger tensorboard)
fi
python scripts/train.py "$TASK" "${ARGS[@]}" "$@"
"$HERE/export_policy.sh"
