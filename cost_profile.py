import json
import math
from pathlib import Path


_REQUIRED_APPLICATION_COSTS = (
    "first_start_delay_seconds",
    "next_rescale_delay_seconds",
    "allocation_update_delay_seconds",
)


def load_cost_profile(path):
    with Path(path).open(encoding="utf-8") as profile_file:
        profile = json.load(profile_file)

    if not isinstance(profile, dict):
        raise ValueError("cost profile root must be a JSON object")

    for key in ("profile_name", "hardware_profile", "network_profile"):
        if not isinstance(profile.get(key), str) or not profile[key].strip():
            raise ValueError("cost profile requires a non-empty '{}'".format(key))

    applications = profile.get("applications")
    if not isinstance(applications, dict) or not applications:
        raise ValueError("cost profile requires a non-empty 'applications' object")

    for app_name, costs in applications.items():
        if not isinstance(costs, dict):
            raise ValueError("cost profile entry for '{}' must be an object".format(app_name))
        for cost_name in _REQUIRED_APPLICATION_COSTS:
            value = costs.get(cost_name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise ValueError(
                    "cost profile '{}' for '{}' must be a finite non-negative number".format(
                        cost_name, app_name
                    )
                )

    bandwidth = profile.get("network_bandwidth_gbps")
    if bandwidth is not None and (
        isinstance(bandwidth, bool)
        or not isinstance(bandwidth, (int, float))
        or not math.isfinite(bandwidth)
        or bandwidth <= 0
    ):
        raise ValueError("'network_bandwidth_gbps' must be a finite positive number")

    interference = profile.get("default_interference")
    if interference is not None and (
        isinstance(interference, bool)
        or not isinstance(interference, (int, float))
        or not math.isfinite(interference)
        or not 0 <= interference < 1
    ):
        raise ValueError("'default_interference' must be in the range [0, 1)")

    return profile
