#!/usr/bin/env bash
# Clone luwu_mjlab at a pinned commit and create the training venv.
# Usage: train/setup_train_env.sh [VENV_DIR]   (default: ~/venvs/mjlab)
# GPU machines: install the CUDA torch wheel for your platform first, then run this.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LUWU_COMMIT=447945fd40fb5585271dce4ea8cc82567916032a
VENV="${1:-$HOME/venvs/mjlab}"
PY="${PYTHON:-python3}"

if [ ! -d "$HERE/luwu_mjlab/.git" ]; then
  git clone https://github.com/LuwuDynamics/luwu_mjlab.git "$HERE/luwu_mjlab"
fi
git -C "$HERE/luwu_mjlab" fetch -q origin
git -C "$HERE/luwu_mjlab" checkout -q "$LUWU_COMMIT"

[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
if ! "$VENV/bin/python" -c "import torch" 2>/dev/null; then
  if command -v nvidia-smi >/dev/null; then
    "$VENV/bin/pip" install -q torch
  else
    "$VENV/bin/pip" install -q torch --index-url https://download.pytorch.org/whl/cpu
  fi
fi
"$VENV/bin/pip" install -q -r "$HERE/requirements.txt"
"$VENV/bin/pip" install -q -e "$HERE/.."
echo "ready: source $VENV/bin/activate && $HERE/train.sh"
