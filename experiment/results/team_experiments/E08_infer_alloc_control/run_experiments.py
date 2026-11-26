import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RESULTS = Path(__file__).resolve().parent
PYTHON = Path(sys.executable).resolve()
COMMIT = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
SEEDS = (11, 22, 33)


def timestamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


for seed in SEEDS:
    for policy_name, random_allocate in (("ats_i", 0), ("random", 1)):
        run_name = f"{policy_name}_seed{seed}_r2"
        run_dir = RESULTS / "runs" / run_name
        output_dir = run_dir / "simulator-output"
        output_dir.mkdir(parents=True, exist_ok=False)
        args = [
            str(PYTHON), "-u", "simulator.py",
            "--workload", "experiment/workload/small.csv",
            "--AFE", "0", "--AISS", "1", "--ARYL", "0",
            "--INFER_SCHEDULER", "1", "--REPAIR_TRAIN", "1",
            "--protect_time", "30", "--interference", "0.0",
            "--interval", "60", "--min-nodes", "16", "--num-gpus", "4",
            "--random_allocate", str(random_allocate), "--policy", "dp",
            "--log_file", "0", "--output", str(output_dir.relative_to(ROOT)),
        ]
        command = "PYTHONHASHSEED=" + str(seed) + " " + " ".join(args)
        (run_dir / "command.txt").write_text(command + "\n", encoding="utf-8")
        metadata = {
            "run": run_name,
            "policy": policy_name,
            "random_allocate": random_allocate,
            "seed": seed,
            "seed_mechanism": "PYTHONHASHSEED; controls Python set iteration order; simulator has no explicit RNG call in this path",
            "command": command,
            "git_commit": COMMIT,
            "python": str(PYTHON),
            "started_at": timestamp(),
            "exit_code": None,
            "runtime_seconds": None,
        }
        (run_dir / "run-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        start = time.monotonic()
        completed = subprocess.run(args, cwd=ROOT, env={**os.environ, "PYTHONHASHSEED": str(seed)},
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        metadata["runtime_seconds"] = round(time.monotonic() - start, 2)
        metadata["ended_at"] = timestamp()
        metadata["exit_code"] = completed.returncode
        (run_dir / "run-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(metadata), flush=True)
        if completed.returncode:
            raise SystemExit(completed.returncode)
