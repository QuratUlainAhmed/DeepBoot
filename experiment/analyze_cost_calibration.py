import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


REQUIRED_COLUMNS = {
    "application",
    "hardware_profile",
    "network_profile",
    "previous_gpus",
    "new_gpus",
    "measured_seconds",
}


def main():
    parser = argparse.ArgumentParser(
        description="Compare simulator rescale-delay predictions with held-out measurements."
    )
    parser.add_argument("--simulator-output", required=True, type=Path)
    parser.add_argument("--measurements", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    jobinfo_path = args.simulator_output / "jobinfo.log"
    with jobinfo_path.open(encoding="utf-8") as jobinfo_file:
        jobinfo = json.load(jobinfo_file)
    profile = jobinfo.get("cost_profile")
    if not isinstance(profile, dict):
        parser.error("jobinfo.log has no cost-profile metadata; run with --cost-profile")

    with args.measurements.open(newline="", encoding="utf-8-sig") as measurements_file:
        reader = csv.DictReader(measurements_file)
        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing_columns:
            parser.error("measurement CSV is missing columns: {}".format(
                ", ".join(sorted(missing_columns))
            ))
        measurements = list(reader)

    predicted = defaultdict(list)
    for job in jobinfo.get("submitted_jobs", []):
        if job["name"].startswith("inference-"):
            continue
        application = job["name"].rsplit("-", 1)[0]
        for event in job.get("rescale_delay_history", []):
            key = (
                application,
                profile["hardware_profile"],
                profile["network_profile"],
                int(event["previous_gpus"]),
                int(event["new_gpus"]),
            )
            predicted[key].append(float(event["predicted_delay_seconds"]))

    measured = defaultdict(list)
    for row_number, row in enumerate(measurements, start=2):
        try:
            key = (
                row["application"].strip(),
                row["hardware_profile"].strip(),
                row["network_profile"].strip(),
                int(row["previous_gpus"]),
                int(row["new_gpus"]),
            )
            value = float(row["measured_seconds"])
        except (TypeError, ValueError) as error:
            parser.error("invalid measurement on CSV row {}: {}".format(row_number, error))
        if not math.isfinite(value) or value < 0:
            parser.error(
                "measured_seconds must be finite and non-negative (row {})".format(
                    row_number
                )
            )
        measured[key].append(value)

    rows = []
    for key in sorted(set(predicted) & set(measured)):
        predicted_mean = sum(predicted[key]) / len(predicted[key])
        measured_mean = sum(measured[key]) / len(measured[key])
        rows.append({
            "application": key[0],
            "hardware_profile": key[1],
            "network_profile": key[2],
            "previous_gpus": key[3],
            "new_gpus": key[4],
            "simulated_event_count": len(predicted[key]),
            "measurement_count": len(measured[key]),
            "predicted_mean_seconds": predicted_mean,
            "measured_mean_seconds": measured_mean,
            "absolute_error_seconds": abs(predicted_mean - measured_mean),
            "signed_error_seconds": predicted_mean - measured_mean,
        })

    if not rows:
        parser.error(
            "no matching application/profile/GPU-transition groups; check profile labels "
            "and application names in the measurements"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with args.output.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    mae = sum(row["absolute_error_seconds"] for row in rows) / len(rows)
    rmse = math.sqrt(
        sum(row["signed_error_seconds"] ** 2 for row in rows) / len(rows)
    )
    print(json.dumps({
        "matched_groups": len(rows),
        "matched_measurements": sum(row["measurement_count"] for row in rows),
        "mean_absolute_error_seconds": mae,
        "root_mean_squared_error_seconds": rmse,
        "comparison_csv": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
