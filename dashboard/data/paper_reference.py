"""Values from the ORIGINAL PAPER (Chen et al., IEEE TPDS 34(9), 2023).

Simulator results in the paper are published only as figures. Every number
below was read by eye from the rendered figure and is APPROXIMATE (about ±0.02 h
on Figs. 9/13/14, ±1 h on Fig. 11b). Source: docs/DEEPBOOT_PAPER_AND_EXPERIMENT_COMPARISON.md §4.3.
Exact values exist only for the testbed (Table II), which is not comparable to
the simulator.
"""

PROVENANCE = "Paper (values read from figures, approximate)"

# Fig. 9 (p. 2562): average TRAINING JCT in hours, simulator, AFE+ATS-I default for DeepBoot.
FIG9_AVG_TRAINING_JCT_H = {
    "Baseline (pure train, 32 GPUs)": {"small": 1.23},
    "Optimus": {"small": 1.30, "middle": 1.57, "large": 1.97},
    "Tiresias": {"small": 0.75, "middle": 1.13, "large": 2.18},
    "AFS": {"small": 0.93, "middle": 1.31, "large": 1.84},
    "Pollux": {"small": 0.55, "middle": 0.70, "large": 1.17},
    "DeepBoot": {"small": 0.66, "middle": 0.77, "large": 1.04},
}

# Fig. 11(b) (p. 2563): makespan in hours.
FIG11B_MAKESPAN_H = {
    "DeepBoot": {"small": 18, "middle": 20, "large": 23},
    "AFS": {"small": 21, "middle": 24, "large": 26},
    "Pollux": {"small": 26, "middle": 44, "large": 74},
}

# Fig. 14 (p. 2564): average training JCT (h) by inference reclaim policy.
FIG14_INFER_POLICY_H = {
    "Random": {"small": 0.72, "middle": 0.83, "large": 1.27},
    "Aryl": {"small": 0.71, "middle": 0.88, "large": 1.10},
    "ATS-I": {"small": 0.67, "middle": 0.77, "large": 1.05},
}

# Fig. 13 (p. 2564): protection-time scale vs average training JCT (h).
FIG13_PROTECT_H = {
    "small": {"0": 0.67, "1x": 0.65, "2x": 0.67, "4x": 0.66},
    "middle": {"0": 0.78, "1x": 0.72, "2x": 0.78, "4x": 0.80},
    "large": {"0": 1.05, "1x": 0.81, "2x": 1.05, "4x": 1.49},
}

# Table I (p. 2554): restart time without / with AFE (s), measured on the testbed.
TABLE1_RESTART_S = {
    "cifar10 (ResNet18)": (38.9, 2.8), "yolov3": (40.8, 3.1), "imagenet (ResNet50)": (149.5, 2.6),
    "bert": (117.8, 5.3), "deepspeech2": (32.6, 1.4), "ncf (NeuMF)": (29.8, None),
}

# Mapping of repository experiments to paper figure points (comparison report §7.1).
REPO_TO_PAPER = [
    {"repo": "E08-rerun", "paper": ("Fig. 9", "DeepBoot", "small"), "match": "Exact or very close reproduction"},
    {"repo": "E04", "paper": ("Fig. 9", "DeepBoot", "middle"), "match": "Partial (AFE off in E04)"},
    {"repo": "E05", "paper": ("Fig. 9", "Pollux", "small"), "match": "Partial (AFE 0, REPAIR_TRAIN 0)"},
    {"repo": "E06", "paper": ("Fig. 9", "AFS", "small"), "match": "Partial (ARYL=1 worker-level reclaim)"},
    {"repo": "E03", "paper": ("Fig. 9", "AFS", "small"), "match": "Partial (ARYL=1, AFE 0)"},
]

KNOWN_CAVEATS = [
    "Workload files contain 20×/100×/200× inference requests per training job; the paper text states 10×/50×/100×.",
    "Restart delays in applications.py differ from the paper's Table I (e.g. ImageNet 35 s vs 149.5 s without AFE).",
    "Scheduler decision time is logged but NOT added to simulated time, so Pollux's makespan penalty (Fig. 11b) cannot appear.",
    "The pure-training baseline (Fig. 9, the paper's '38%' claim) was never run in this repository.",
    "The repository's 'RANDOM' inference path is hash-ordered first-fit; it uses no random number generator.",
    "AFS runs (E03/E06) used ARYL=1 (Aryl worker-level reclaiming), as in the authors' launcher.",
    "Most configurations were run once; determinism is proven only for dp + ATS-I + AFE=0.",
    "E02 has no command record and its verified rerun (E08-rerun) gives a different result.",
]
