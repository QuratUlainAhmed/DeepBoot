import unittest

import numpy as np

from infer_scheduler import InferScheduler


class JobInfoStub(object):
    inference = False

    def __init__(self, restart_cost_seconds, current_replicas,
                 num_restarts, run_time):
        self.restart_cost_seconds = restart_cost_seconds
        self.current_replicas = current_replicas
        self.num_restarts = num_restarts
        self.run_time = run_time
        self.speedup_fn = lambda num_nodes, num_replicas: num_replicas


class SizeAwareInferenceSchedulerTest(unittest.TestCase):
    def test_priority_combines_restart_cost_restarts_and_execution_time(self):
        scheduler = InferScheduler(size_aware_scheduling=True)
        expensive_job = JobInfoStub(100, 4, 10, 1000)
        low_cost_job = JobInfoStub(10, 1, 1, 100)

        priorities = scheduler._get_training_priority_weights(
            [expensive_job, low_cost_job]
        )

        self.assertGreater(priorities[0], priorities[1])
        self.assertAlmostEqual(priorities[0], 1.5)

    def test_atsi_reclaims_gpu_from_lower_priority_job(self):
        scheduler = InferScheduler(size_aware_scheduling=True)
        protected_job = JobInfoStub(100, 4, 10, 1000)
        reclaimable_job = JobInfoStub(10, 1, 1, 100)
        scheduler.job_vals = [protected_job, reclaimable_job]
        scheduler.training_priority_weights = scheduler._get_training_priority_weights(
            scheduler.job_vals
        )
        scheduler.training_state = np.array([[1], [1]], dtype=int)
        scheduler.node_training_gpus = np.array([2])
        scheduler.node_infer_gpus = np.array([0])
        scheduler.node_sleep_gpus = np.array([0])
        scheduler.num_training_jobs = 2
        scheduler.num_nodes = 1
        scheduler.num_training_gpus = 2
        scheduler.remain_infer_tasks = 1
        scheduler.curr_infer_job_id = 0
        scheduler.update_state = np.zeros((1, 1), dtype=int)
        scheduler.best_cases = []

        scheduler._schedule_training_gpu()

        self.assertEqual(scheduler.training_state[:, 0].tolist(), [1, 0])
        self.assertEqual(scheduler.update_state[0, 0], 1)

    def test_feature_disabled_keeps_equal_reclaim_weights(self):
        scheduler = InferScheduler()
        priorities = scheduler._get_training_priority_weights(
            [JobInfoStub(100, 4, 10, 1000), JobInfoStub(10, 1, 1, 100)]
        )

        self.assertEqual(priorities.tolist(), [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
