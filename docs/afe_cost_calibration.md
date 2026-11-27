# Calibrating AFE Costs for Hardware and Network Profiles

## Initial behavior

Before this change, the simulator used repository-wide per-application delay
constants from `applications.py`. With AFE enabled,
`Job.calculate_rescale_time` used `FIRST_DELAY` and `NEXT_DELAY` to estimate
rescale delay from the before/after GPU counts. With AFE disabled, allocation
changes used `APPLICATIONS_DELAY`. The simulator's interference default was
zero. These defaults do not identify a particular hardware or network profile,
and per-job output did not retain the predicted delay for each allocation
change.

## Changes made

1. **Added measured cost-profile input.** `--cost-profile path.json` accepts
   profile metadata (`profile_name`, `hardware_profile`, `network_profile`,
   optional `network_bandwidth_gbps`, optional `default_interference`) and
   per-application measured values:
   - `first_start_delay_seconds`
   - `next_rescale_delay_seconds`
   - `allocation_update_delay_seconds`
2. **Applied profile costs to training jobs.** AFE's existing allocation-size
   interpolation now uses the selected profile's measured first-start and
   next-rescale delay values. Non-AFE allocation updates use the profile's
   allocation-update delay. Applications missing from the profile explicitly
   warn and retain the repository defaults.
3. **Made interference profile-aware.** If `--interference` is omitted, the
   simulator uses the profile's optional default or the original 0.0 default.
   An explicit CLI value overrides the profile. Values outside `[0, 1)` are
   rejected.
4. **Recorded provenance and predictions.** The selected profile is copied to
   the output folder as `cost-profile.json` and included in `jobinfo.log`.
   Training job records now include each allocation transition, before/after
   GPU counts, the predicted delay, and whether AFE was enabled.
5. **Added held-out comparison tooling.** `experiment/analyze_cost_calibration.py`
   compares simulator transition predictions with independently collected
   measurements and reports per-transition errors plus aggregate MAE and RMSE.

The profile records metadata describing the hardware and network where its
measurements were collected. The simulator does **not** invent a formula that
scales delay from bandwidth or GPU model; create a separate measured profile
for each environment. The profile parameters must be calibrated from
measurements, not copied from the old constants and presented as new measured
data.

## Profile format

```json
{
  "profile_name": "replace-with-measurement-set-name",
  "hardware_profile": "replace-with-GPU-and-host-description",
  "network_profile": "replace-with-network-description",
  "network_bandwidth_gbps": null,
  "default_interference": null,
  "applications": {
    "bert": {
      "first_start_delay_seconds": 0.0,
      "next_rescale_delay_seconds": 0.0,
      "allocation_update_delay_seconds": 0.0
    }
  }
}
```

The zero values above are schema placeholders, **not measured results**. Replace
them with repeatable measurements before running a calibrated simulation.
`null` means bandwidth/interference metadata was not supplied; supply an actual
measurement when available. Use one profile per hardware/network combination
and include every training application in the workload. Missing applications
generate an explicit warning and use repository defaults for those applications.

For AFE, the existing simulator maps measured `first_start_delay_seconds` and
`next_rescale_delay_seconds` into its current scale-up/scale-down formula.
`allocation_update_delay_seconds` is used when AFE is disabled.

## Collecting validation measurements

For each application and profile, collect repeated wall-clock durations for:

- First start / initialization.
- Rescaling with different previous and new GPU counts.
- Allocation update without AFE, if that mode will be compared.
- Optionally, representative runs with measured contention/interference.

Keep calibration runs separate from validation runs. Use calibration measurements
to construct the profile, then use held-out validation measurements for the
comparison. Do not compare a profile against the exact same measurements used
to populate it and call that independent validation.

Create a CSV with these columns:

```text
application,hardware_profile,network_profile,previous_gpus,new_gpus,measured_seconds
```

`application` must match the workload's training application name. GPU counts
identify the transition being validated; use `previous_gpus=0` for first
allocation. Record multiple rows per transition when possible.

## Run and compare

From the repository root, create a profile JSON using measured data, then run:

```powershell
python simulator.py `
  --workload experiment/workload/small.csv `
  --policy dp --AFE 1 --AISS 1 --min-nodes 16 --num-gpus 4 `
  --cost-profile path\to\measured-profile.json `
  --output experiment\results\cost-calibration\run-01
```

Use the project's Python environment with its simulator dependencies. Provide
`--interference value` to override the profile default explicitly.

Compare against held-out testbed measurements:

```powershell
python experiment/analyze_cost_calibration.py `
  --simulator-output experiment\results\cost-calibration\run-01 `
  --measurements path\to\held-out-measurements.csv `
  --output experiment\results\cost-calibration\run-01\calibration-comparison.csv
```

The CSV reports predicted and observed group means, counts, signed/absolute
errors. The console summary reports mean absolute error (MAE) and root mean
squared error (RMSE) across matched application/profile/GPU-transition groups.
Rows with no corresponding simulated transition are not scored; the tool fails
if there are no matching groups.

## Limitations

- Calibration quality depends on consistent instrumentation and enough repeated
  samples. Record the measurement method and run conditions alongside the data.
- GPU/network labels are metadata and selection keys, not a physical resource
  model. The simulator still represents homogeneous nodes and applies the
  existing simplified slowdown model.
- The existing AFE interpolation formula is retained. The change supplies
  measured delay parameters but does not validate or replace that formula.
- The current simulator's interference factor is a scalar throughput slowdown;
  it does not model network contention as a separate time-varying resource.
- Run controlled comparisons with the same workload, scheduler flags, and
  hardware profile before attributing JCT differences to calibration.

## Files changed

- `cost_profile.py`: parse and validate profile metadata and measurements.
- `simulator.py`: apply profile delay/interference values and retain profile and
  per-transition predicted delay in run output.
- `experiment/analyze_cost_calibration.py`: compare output predictions with
  held-out testbed measurements.
- `tests/test_cost_profile.py`: profile validation tests.
