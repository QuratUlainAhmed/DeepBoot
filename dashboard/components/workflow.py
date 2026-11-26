"""Graphviz (DOT) diagrams of the scheduling components, grounded in code.

Solid nodes = implemented in this repository (file:line given).
Dashed pink nodes = described in the paper only (not in the simulator).
"""

COMPONENTS_DOT = r"""
digraph G {
  bgcolor="transparent"; rankdir=TB; nodesep=0.5; ranksep=0.45;
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#475569", fillcolor="#1E293B", fontcolor="#E2E8F0"];
  edge [color="#64748B", fontname="Helvetica", fontsize=9, fontcolor="#94A3B8"];

  loop [label="Simulator loop (1 s clock)\nsimulator.py:1095", fillcolor="#0F172A"];
  ev   [label="event_update()\n60 s tick | arrival/finish |\nwaiting inference + warm pod\nsimulator.py:1029"];
  pods [label="update_infer_pod_status()\nRUNNING→PROTECT→SLEEP\nsimulator.py:521"];
  atst [label="ATS-T  (policy dp)\nDeepBoot.optimize → allocate_elastic\n→ max_value_dp (group knapsack)\ndp.py:161,111,88", fillcolor="#1D4ED8"];
  atsi [label="ATS-I\nInferScheduler.ATSI_infer_schedule\nempty → SLEEP → reclaim best ΔSPEEDUP\ninfer_scheduler.py:455,113,200", fillcolor="#B45309"];
  rnd  [label="RANDOM path (--random_allocate 1)\nhash-ordered first-fit, no RNG\ninfer_scheduler.py:359", fillcolor="#334155"];
  warm [label="Warm-pod reuse (same app)\nJob.step  simulator.py:200-236", fillcolor="#6B21A8"];
  aiss [label="AISS flag\n1: finished pod → PROTECT (reusable)\n0: finished pod deleted (6 s cold start)\nsimulator.py:333,533-553", fillcolor="#6B21A8"];
  afe  [label="AFE flag → rescale delay model\nJob.reallocate / calculate_rescale_time\nsimulator.py:339,389", fillcolor="#047857"];
  real [label="Job.step: training progress\npaused while rescale_time > 0", fillcolor="#0F172A"];
  sync [label="Paper only: Redis sync flags,\nrank-0 save/load state,\nPod lifecycle (Sec. V)", style="rounded,dashed,filled", fillcolor="#3B0A2A", color="#F472B6", fontcolor="#F9A8D4"];

  loop -> pods -> ev;
  ev -> atst [label="clock % 60 == 0"];
  ev -> atsi [label="other events\n(INFER_SCHEDULER=1)"];
  ev -> rnd  [label="if random_allocate=1", style=dashed];
  ev -> warm [label="inference job.step"];
  aiss -> warm [label="enables"];
  aiss -> pods [label="controls"];
  atst -> afe [label="allocation changed"];
  atsi -> afe [label="training GPU reclaimed"];
  afe -> real;
  afe -> sync [style=dashed, color="#F472B6", label="abstracted as\na delay number"];
}
"""

POD_LIFECYCLE_DOT = r"""
digraph P {
  bgcolor="transparent"; rankdir=LR;
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#475569", fontcolor="#E2E8F0"];
  edge [color="#64748B", fontname="Helvetica", fontsize=9, fontcolor="#94A3B8"];
  new [label="new pod\n(cold start 6 s)", fillcolor="#1E293B"];
  run [label="RUNNING", fillcolor="#B45309"];
  pro [label="PROTECT\nlive_time = min(30+15·reuse, 120)·protect_times", fillcolor="#6B21A8"];
  slp [label="SLEEP\n(GPU reclaimable by ATS-T)", fillcolor="#475569"];
  gone [label="deleted", fillcolor="#0F172A"];
  new -> run;
  run -> pro [label="finished, AISS=1"];
  run -> gone [label="finished, AISS=0"];
  pro -> run [label="same-app request\nreuse count +1"];
  pro -> slp [label="live_time expires"];
  slp -> run [label="same-app request\nreuse count reset"];
  slp -> gone [label="GPU taken / popped"];
}
"""
