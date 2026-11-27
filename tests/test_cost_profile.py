import json
import tempfile
import unittest
from pathlib import Path

import pandas

from cost_profile import load_cost_profile
import simulator
from dp import DeepBoot


class CostProfileTest(unittest.TestCase):
    def write_profile(self, profile):
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        )
        with temp_file:
            json.dump(profile, temp_file)
        self.addCleanup(Path(temp_file.name).unlink)
        return temp_file.name

    def valid_profile(self):
        return {
            "profile_name": "measured-lab",
            "hardware_profile": "P40-node",
            "network_profile": "10GbE",
            "network_bandwidth_gbps": 10,
            "default_interference": 0.1,
            "applications": {
                "bert": {
                    "first_start_delay_seconds": 30,
                    "next_rescale_delay_seconds": 8,
                    "allocation_update_delay_seconds": 20,
                }
            },
        }

    def test_loads_profile_with_measured_costs_and_metadata(self):
        profile = load_cost_profile(self.write_profile(self.valid_profile()))

        self.assertEqual(profile["hardware_profile"], "P40-node")
        self.assertEqual(
            profile["applications"]["bert"]["next_rescale_delay_seconds"], 8
        )

    def test_rejects_negative_delay(self):
        profile = self.valid_profile()
        profile["applications"]["bert"]["next_rescale_delay_seconds"] = -1

        with self.assertRaises(ValueError):
            load_cost_profile(self.write_profile(profile))

    def test_rejects_invalid_default_interference(self):
        profile = self.valid_profile()
        profile["default_interference"] = 1

        with self.assertRaises(ValueError):
            load_cost_profile(self.write_profile(profile))

    def test_profile_costs_reach_simulated_training_job(self):
        workload = pandas.DataFrame([{
            "name": "bert-calibration-test",
            "application": "bert",
            "time": 0,
            "duration": 0,
        }])
        profile = self.valid_profile()
        original_afe = simulator.AFE
        simulator.AFE = 1
        self.addCleanup(setattr, simulator, "AFE", original_afe)

        cluster = simulator.Cluster(
            workload, DeepBoot(), min_nodes=1, num_gpus=4, cost_profile=profile
        )
        job = cluster.jobs[0]

        self.assertEqual(job.calculate_rescale_time([], [1]), 30)
        self.assertEqual(job.calculate_rescale_time([1], [1, 1]), 19)

        baseline = simulator.Cluster(
            workload, DeepBoot(), min_nodes=1, num_gpus=4
        ).jobs[0]
        self.assertEqual(
            baseline.first_start_delay, simulator.FIRST_DELAY["bert"]
        )


if __name__ == "__main__":
    unittest.main()
