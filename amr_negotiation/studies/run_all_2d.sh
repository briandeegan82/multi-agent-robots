#!/usr/bin/env bash
# Reruns every 2D study on the checked-out commit and refreshes studies/results_raw/ and studies/report/.
# Usage (from anywhere): bash amr_negotiation/studies/run_all_2d.sh      ~20 min on 8 cores
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=$PWD
if [ -n "$(git status --porcelain -- amr_negotiation rulebooks scenarios studies/*.py)" ]; then
  echo "uncommitted code changes: commit first so results_raw/COMMIT names the code that produced the data" >&2; exit 1
fi
COMMIT=$(git rev-parse --short HEAD)
OUT=studies/results RAW=studies/results_raw REP=studies/report
python studies/run_studies.py $OUT
python studies/run_studies_r2.py $OUT
for f in $OUT/*.csv; do gzip -nc "$f" > "$RAW/$(basename "$f").gz"; done
python studies/analyse.py $OUT && cp $OUT/results.md $REP/ && cp $OUT/fig/S1_* $OUT/fig/S3_* $REP/fig/
python studies/analyse_r2.py $OUT && cp $OUT/results_r2.md studies/report_r2/ && cp $OUT/fig/S7_* $OUT/fig/S8_* studies/report_r2/fig/
python studies/analyse_payments.py $OUT && cp $OUT/payments.md studies/report_r2/
python studies/analyse_protocol.py studies
python studies/reservation_baseline.py studies
python studies/explore_map.py > $REP/explore_map.md
python studies/convoy_group.py > $REP/convoy_group.txt
python studies/tjunction_goal.py $REP/tjunction_goal.txt
python studies/asym_map.py > $REP/asym_map.txt
python studies/wrong_map.py > $REP/wrong_map.md
python studies/learned_negotiator.py
echo "$COMMIT" > $RAW/COMMIT
echo "done: every file in $RAW and $REP regenerated at $COMMIT"
