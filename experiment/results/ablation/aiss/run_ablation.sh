#!/bin/bash
# AISS ablation: ONLY --AISS differs. All other flags are identical to DeepBoot-small-ATSI.sh
cd "$(git rev-parse --show-toplevel)"
BASE=experiment/results/ablation/aiss
LOGS=$HOME/E03_logs
for A in 0 1; do
  if [ -n "$(ls -A $BASE/aiss-$A 2>/dev/null)" ]; then echo "$BASE/aiss-$A is not empty, aborting"; exit 1; fi
done
git rev-parse HEAD > $BASE/commit.txt
for A in 0 1; do
  OUT=$BASE/aiss-$A
  mkdir -p $OUT
  CMD="python3 simulator.py --workload ./experiment/workload/small.csv --AFE 0 --AISS $A --log_file 0 --output $OUT --min-nodes 16 --num-gpus 4 --policy dp"
  echo "$CMD" > $OUT/command.txt
  (
    date -Iseconds > $OUT/start_time.txt
    /usr/bin/time -v -o $OUT/time_v.txt $CMD > $LOGS/aiss-$A.log 2>&1
    echo "exit_code=$?" > $OUT/exit_status.txt
    date -Iseconds > $OUT/end_time.txt
  ) &
done
wait
echo "both runs finished"
