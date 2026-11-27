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


# ----------------------------------------------------------------- step story
# Builds the "What's happening inside DeepBoot?" cards. Every field comes from
# the step record (controller events + instrumentation decisions) or from job
# attributes of the research Cluster. Nothing is inferred beyond that.
ACCENT = {"ATS-T": "#3B82F6", "AFE": "#60A5FA", "ATS-I": "#F59E0B", "AISS": "#A855F7", "ARRIVAL": "#22D3EE",
          "DONE": "#34D399", "TRAIN": "#3B82F6"}
_ACC_CLASS = {"#3B82F6": "acc-blue", "#60A5FA": "acc-lblue", "#F59E0B": "acc-amber", "#A855F7": "acc-purple",
              "#22D3EE": "acc-cyan", "#34D399": "acc-green", "#94A3B8": "acc-grey"}
_RESCALE = ("training-scale-up", "training-scale-down", "training-migrate", "training-preempted")


def fmt_alloc(a) -> str:
    from collections import Counter
    return "{" + ", ".join(f"w{k}:{v}" for k, v in sorted(Counter(a).items())) + "}" if a else "∅"


def _more(items, n=4):
    items = list(items)
    return items[:n], max(len(items) - n, 0)


def step_story(rec: Dict, ctl) -> List[Dict]:
    """Cards (most significant first) describing one real scheduling step."""
    c, cfg = ctl.cluster, ctl.cfg
    evs = rec.get("events", [])
    by = {}
    for e in evs:
        by.setdefault(e["type"], []).append(e)
    decs = rec.get("decisions", [])
    alloc_now = ctl.snapshots[-1]["allocations"] if ctl.snapshots else {}
    cards: List[Dict] = []

    def job(name):
        return c.job_dict.get(name)

    # ---- ATS-T (dp.py) decision
    for d in [d for d in decs if d["kind"] == "ATS-T"]:
        prev, new = d.get("prev_alloc", {}), d.get("new_alloc", {})
        changed = [(j["job"], prev.get(j["job"], []), new.get(j["job"], [])) for j in d.get("jobs", [])
                   if sorted(prev.get(j["job"], [])) != sorted(new.get(j["job"], []))]
        kv = [("Training jobs considered", str(len(d.get("jobs", [])))),
              ("GPUs available to training", f"{d.get('capacity')} (not held by inference pods)")]
        shown, extra = _more(changed)
        for name, a0, a1 in shown:
            kv.append((name, f"{len(a0)} → <b>{len(a1)}</b> GPUs &nbsp;<code>{fmt_alloc(a0)}</code> → <code>{fmt_alloc(a1)}</code>"))
        if extra:
            kv.append(("…", f"{extra} more change(s) in the details below"))
        if not changed:
            kv.append(("Decision", "kept every training job's allocation unchanged"))
        cards.append({"rank": 1 if changed else 9, "tag": "ATS-T · dp.py", "acc": ACCENT["ATS-T"],
                      "title": "ATS-T evaluated the available resources and selected an allocation.",
                      "kv": kv, "note": "Group knapsack (<code>DeepBoot.max_value_dp</code>): one option per job "
                      "(1…max_replicas GPUs), valued by SPEEDUP × restart penalty. This is ATS-T's output; "
                      "the grid shows the final allocation after the whole step."})

    # ---- training allocation changes not covered by an ATS-T record (other policies)
    tr_change = [e for e in evs if e["type"] in _RESCALE + ("training-start",)]
    if tr_change and not any(d["kind"] == "ATS-T" for d in decs) and not any(d["kind"] == "ATS-I" and d.get("reclaims") for d in decs):
        if rec.get("tick") or not cfg.INFER_SCHEDULER:
            tag, title = f"{cfg.policy} scheduler", f"The training scheduler ({cfg.policy}) changed training allocations."
            note = f"Path: <code>{rec['path']}</code>."
        else:
            tag, title = "Side effect", "Training allocation changed during an inference-scheduling step."
            note = (f"Path: <code>{rec['path']}</code>. Training GPUs were displaced by inference placement "
                    + ("(RANDOM path: <code>update_alloc</code> drops replicas on GPUs it hands to inference)."
                       if cfg.random_allocate else "(no reclaim record was produced for it)."))
        cards.append({"rank": 2, "tag": tag, "acc": ACCENT["TRAIN"], "title": title,
                      "kv": [(e["job"], f"{e['gpus_before']} → <b>{e['gpus_after']}</b> GPUs") for e in tr_change[:5]],
                      "note": note})

    # ---- rescaling / AFE
    resc = [e for e in tr_change if e.get("gpus_after", 0) > 0 or e["type"] == "training-preempted"]
    if resc:
        only_start = all(e["type"] == "training-start" for e in resc)
        if only_start:
            title = "Training job started on its allocated GPUs."
        elif cfg.AFE:
            title = "AFE is adjusting the training allocation."
        else:
            title = "Training allocation rescaled (AFE off: stop-and-restart delay model)."
        kv = []
        shown, extra = _more(resc)
        for e in shown:
            a0 = "start" if e["type"] == "training-start" else f"{e['gpus_before']}"
            txt = f"{a0} → <b>{e['gpus_after']}</b> GPUs"
            if e["gpus_after"]:
                txt += f" · rescale delay <b>{e.get('rescale_delay', 0)} s</b>"
            else:
                txt += " · preempted (no GPUs)"
            j = job(e["job"])
            if j is not None and j.num_restarts:
                txt += f" · restarts {j.num_restarts}"
            kv.append((e["job"], txt))
        if extra:
            kv.append(("…", f"{extra} more"))
        cards.append({"rank": 3 if only_start else 2, "tag": "AFE · rescale model" if cfg.AFE else "Rescale (AFE off)",
                      "acc": ACCENT["AFE"], "title": title, "kv": kv,
                      "note": "The simulator models a rescale as a delay (<code>Job.calculate_rescale_time</code>, "
                      + ("AFE first/next delays" if cfg.AFE else "stop-resume baseline delays")
                      + "); training progress pauses while it counts down. State save/load and worker "
                      "synchronisation are not simulated step by step."})

    # ---- inference arrival / ATS-I placement / reclamation
    inf_arr = [e for e in by.get("arrival", []) if job(e["job"]) is not None and job(e["job"]).inference]
    placed = by.get("inference-placement", [])
    warm = by.get("warm-reuse", [])
    atsi = [d for d in decs if d["kind"] in ("ATS-I", "RANDOM") and (d.get("placed") or d.get("branches"))]
    if inf_arr or placed or warm or atsi:
        reclaims = [r for d in atsi for r in d.get("reclaims", [])]
        if reclaims:
            title = "ATS-I reclaimed training GPUs to serve inference."
        elif inf_arr:
            title = "New inference workload submitted." if len(inf_arr) == 1 else f"{len(inf_arr)} new inference requests submitted."
        else:
            title = "Waiting inference request(s) placed."
        kv = []
        shown, extra = _more(inf_arr, 3)
        for e in shown:
            j = job(e["job"])
            kv.append(("Request", f"<b>{e['job']}</b> · {j.app} · arrived t={j.submission_time} s"))
        if extra:
            kv.append(("…", f"{extra} more request(s)"))
        branches = [b for d in atsi for b in d.get("branches", [])]
        if branches:
            kv.append(("ATS-I branch", ", ".join(f"{b['count']}× {b['branch']}" for b in branches)))
        if any(d["kind"] == "RANDOM" for d in atsi):
            kv.append(("Path", "RANDOM allocator (<code>--random_allocate 1</code>)"))
        for e in placed[:4]:
            kv.append(("Placed", f"{e['job']} on <code>{e['detail'].split('→')[-1].strip()}</code>"))
        for e in warm[:3]:
            j = job(e["job"])
            kv.append(("Warm reuse", f"{e['job']} reuses pod <b>{j.pod_name}</b> (no cold start)"))
        for r in reclaims[:4]:
            kv.append(("Reclaimed", f"{r.get('gpus', 1)} GPU from <b>{r['training_job']}</b> on worker {r['node']}"))
        served = {e["job"] for e in placed} | {e["job"] for e in warm}
        waiting = [e["job"] for e in inf_arr if e["job"] not in served and e["job"] not in alloc_now]
        if waiting:
            kv.append(("Still queued", ", ".join(waiting[:4]) + (" …" if len(waiting) > 4 else "")))
        note = ("ATS-I order: empty GPU → SLEEP-pod GPU → reclaim the training GPU whose loss keeps the highest "
                "total remaining SPEEDUP.") if not any(d["kind"] == "RANDOM" for d in atsi) else \
            "RANDOM path: first-fit by set order, no speedup criterion."
        is_rand = any(d["kind"] == "RANDOM" for d in atsi) or (cfg.random_allocate and not atsi)
        cards.append({"rank": 0 if reclaims else 4, "acc": ACCENT["ATS-I"],
                      "tag": "RANDOM · infer_scheduler.py" if is_rand else "ATS-I · infer_scheduler.py",
                      "title": title, "kv": kv, "note": note})

    # ---- training arrivals
    tr_arr = [e for e in by.get("arrival", []) if job(e["job"]) is not None and not job(e["job"]).inference]
    if tr_arr:
        kv = []
        for e in tr_arr[:4]:
            j = job(e["job"])
            n = len(alloc_now.get(e["job"], []))
            status = f"allocated {n} GPU(s) in this step" if n else "pending (no GPUs yet)"
            kv += [("Job", f"<b>{j.name}</b>"), ("Application", j.app), ("Arrival time", f"t = {j.submission_time} s"),
                   ("Initial status", status)]
        note = None
        if not rec.get("tick") and cfg.INFER_SCHEDULER:
            note = (f"This step ran <code>{rec['path']}</code>. Training allocations are recomputed by the training "
                    f"scheduler at the {cfg.interval} s tick.")
        cards.append({"rank": 5, "tag": "Arrival", "acc": ACCENT["ARRIVAL"],
                      "title": "New training job submitted." if len(tr_arr) == 1 else f"{len(tr_arr)} new training jobs submitted.",
                      "kv": kv, "note": note})

    # ---- completions
    done = by.get("completion", [])
    tr_done = [e for e in done if job(e["job"]) is not None and not job(e["job"]).inference]
    inf_done = [e for e in done if e not in tr_done]
    if tr_done:
        cards.append({"rank": 6, "tag": "Completed", "acc": ACCENT["DONE"],
                      "title": "Training job finished and released its GPUs." if len(tr_done) == 1 else f"{len(tr_done)} training jobs finished.",
                      "kv": [(e["job"], e["detail"]) for e in tr_done[:4]], "note": None})

    # ---- AISS lifecycle (only recorded transitions)
    pod_ev = by.get("pod-state", []) + by.get("pod-removed", [])
    if pod_ev:
        kv = []
        for e in pod_ev[:5]:
            if e["type"] == "pod-state":
                kv.append((e["job"], e["detail"].split(": ", 1)[-1]))
            else:
                kv.append((e["job"], "pod deleted"))
        if len(pod_ev) > 5:
            kv.append(("…", f"{len(pod_ev) - 5} more transition(s)"))
        cards.append({"rank": 7, "tag": "AISS · pod lifecycle" if cfg.AISS else "Pod lifecycle (AISS off)",
                      "acc": ACCENT["AISS"], "title": "Inference pod lifecycle changed.", "kv": kv,
                      "note": "RUNNING → PROTECT: finished pod stays warm and reserved for same-app requests. "
                      "PROTECT → SLEEP: protection time expired, GPU becomes reclaimable. "
                      "(<code>Cluster.update_infer_pod_status</code>)" if cfg.AISS else
                      "With AISS=0 a finished pod is deleted; the next request of that app pays the cold start."})
    if inf_done:
        cards.append({"rank": 8, "tag": "Completed", "acc": ACCENT["DONE"],
                      "title": "Inference request(s) finished." if len(inf_done) > 1 else "Inference request finished.",
                      "kv": [(e["job"], e["detail"]) for e in inf_done[:4]], "note": None})

    cards.sort(key=lambda x: x["rank"])
    return cards


def story_card_html(card: Dict, main: bool = False) -> str:
    kv = "".join(f"<i>{k}</i><span>{v}</span>" for k, v in card["kv"])
    note = f'<div class="note">{card["note"]}</div>' if card.get("note") else ""
    acc = _ACC_CLASS.get(card["acc"], "acc-grey")
    return (f'<div class="db-story {acc}{" main" if main else ""}">'
            f'<div class="tag">{card["tag"]}</div><div class="ttl">{card["title"]}</div>'
            f'<div class="kv">{kv}</div>{note}</div>')
