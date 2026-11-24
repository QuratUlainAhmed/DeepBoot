# Run notes
Both runs were launched together by run_ablation.sh, in parallel on one laptop (8 CPUs, 7 GB RAM).
The run folders contain only the simulator outputs plus exit_status.txt and end_time.txt. command.txt,
start_time.txt and time_v.txt were not present after the runs, so wall-clock time and peak memory
were not recorded. The likely cause is that the simulator clears its output folder at startup (not verified in code).
Launch time was about 17:35 (from log file timestamps); end times are in aiss-*/end_time.txt.

Commands (reconstructed from run_ablation.sh; only --AISS differs):
python3 simulator.py --workload ./experiment/workload/small.csv --AFE 0 --AISS {0|1} --log_file 0 --output <dir> --min-nodes 16 --num-gpus 4 --policy dp

The full console logs (hundreds of MB each) are kept outside the repo in ~/E03_logs/.
