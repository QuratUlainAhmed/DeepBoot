"""Plain-language narration of REAL simulator step records (no invented content)."""
from __future__ import annotations

from typing import Dict, List

ICONS = {
    "arrival": "📥", "submitted": "📝", "completion": "✅", "training-start": "▶️", "training-scale-up": "⬆️",
    "training-scale-down": "⬇️", "training-migrate": "🔀", "training-preempted": "⛔", "training-released": "🏁",
    "inference-placement": "⚡", "inference-release": "↩️", "warm-reuse": "♻️", "pod-state": "🔁",
    "pod-removed": "🗑️",
}


def narrate_decision(d: Dict) -> str:
    k = d.get("kind")
    if k == "ATS-T":
        ks = d.get("knapsack") or {}
        chosen = ks.get("chosen_replicas", [])
        jobs = d.get("jobs", [])
        changes = [f"{j['job']}: {j['prev_gpus']}→{w}" for j, w in zip(jobs, chosen) if j["prev_gpus"] != w]
        return (f"**ATS-T** (dp.py) solved a group knapsack: {len(jobs)} training job(s) competing for "
                f"{d.get('capacity')} GPU(s) not held by inference pods. Each job's options were 1…max_replicas GPUs, "
                f"valued by SPEEDUP × restart-penalty factor. "
                + (f"Replica-count changes: {', '.join(changes)}." if changes else "No replica-count change."))
    if k == "ATS-I":
        br = ", ".join(f"{b['count']}× {b['branch']}" for b in d.get("branches", [])) or "no new placement"
        txt = f"**ATS-I** (infer_scheduler.py) placed waiting inference request(s): {br}."
        if d.get("reclaims"):
            rc = "; ".join(f"took a GPU from **{r['training_job']}** on worker {r['node']}" for r in d["reclaims"])
            txt += f" No empty or SLEEP GPU was left, so it reclaimed from training: {rc}."
            srch = d.get("reclaim_search") or []
            if srch:
                txt += (" Each reclaim enumerated every feasible (training job, worker) GPU and kept the one with "
                        "the highest remaining total SPEEDUP ("
                        + ", ".join(f"{s['candidates']} candidates → best Σ={s['best_remaining_speedup_sum']}" for s in srch)
                        + ").")
        if d.get("aryl"):
            txt += " (ARYL=1: Aryl worker-level ordering/eviction.)"
        return txt
    if k == "RANDOM":
        return (f"**RANDOM path** (infer_scheduler.random_allocate) placed {len(d.get('placed', {}))} request(s) "
                "by Python set order onto the free-GPU list. That list can include GPUs held by training; displaced "
                "training replicas are dropped by update_alloc. No speedup criterion is used.")
    return str(d)


def event_line(e: Dict) -> str:
    return f"{ICONS.get(e['type'], '•')} `t={e['clock']}` **{e['type']}** · {e['job']}: {e['detail']}"


def summarize_step(rec: Dict) -> List[str]:
    out = [f"Scheduler call: `{rec['path']}`"
           + (f" · wall time {rec['optimize_wall_s']:.3f} s (not added to simulated time)" if rec.get("optimize_wall_s") is not None else "")]
    out += [narrate_decision(d) for d in rec.get("decisions", [])]
    return out
