"""GPU cluster grid built from a controller snapshot.

The research simulator tracks allocations as `job -> [node, node, ...]`, i.e. a
COUNT of GPUs per worker per job. Individual GPUs have no identity. The grid
therefore fills each worker's slots in a fixed order (training, inference
RUNNING, PROTECT, SLEEP, idle); slot position within a worker is illustrative,
while the per-worker counts are exactly the simulator's.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List

import plotly.graph_objects as go

from .theme import COLORS, LABELS

ORDER = ["training", "training_rescaling", "inference_running", "inference_protect", "inference_sleep"]


def slot_table(snapshot: dict, num_nodes: int, gpus_per_node: int) -> List[Dict]:
    pods = snapshot.get("pods", {})
    rescaling = set(snapshot.get("rescaling", []))
    per_node: Dict[int, List[Dict]] = {n: [] for n in range(num_nodes)}
    for job, alloc in snapshot["allocations"].items():
        if job.startswith("inference"):
            st = pods.get(job, {}).get("status", "RUNNING")
            cat = {"PROTECT": "inference_protect", "SLEEP": "inference_sleep"}.get(st, "inference_running")
            detail = pods.get(job, {})
        else:
            cat = "training_rescaling" if job in rescaling else "training"
            detail = {}
        for node, cnt in Counter(alloc).items():
            for _ in range(cnt):
                per_node[int(node)].append({"job": job, "cat": cat, "pod": detail})
    rows = []
    for n in range(num_nodes):
        items = sorted(per_node[n], key=lambda d: (ORDER.index(d["cat"]), d["job"]))
        for s in range(gpus_per_node):
            if s < len(items):
                rows.append({"node": n, "slot": s, **items[s]})
            else:
                rows.append({"node": n, "slot": s, "job": "", "cat": "idle", "pod": {}})
        if len(items) > gpus_per_node:  # should never happen; surfaced rather than hidden
            rows.append({"node": n, "slot": gpus_per_node, "job": "OVERCOMMIT", "cat": "idle", "pod": {}})
    return rows


def cluster_figure(snapshot: dict, num_nodes: int, gpus_per_node: int, highlight_job: str = "") -> go.Figure:
    rows = slot_table(snapshot, num_nodes, gpus_per_node)
    half = num_nodes // 2
    xs, ys, colors, texts, hovers, custom, lines = [], [], [], [], [], [], []
    for r in rows:
        col = 0 if r["node"] < half else 1
        x = r["slot"] + col * (gpus_per_node + 1.6)
        y = -(r["node"] % half if num_nodes > 1 else 0)
        xs.append(x)
        ys.append(y)
        colors.append(COLORS[r["cat"]])
        if r["job"].startswith("inference-"):  # inference-<model>-<n>  ->  <model[:5]>·<n>
            parts = r["job"].split("-")
            texts.append(f"{parts[1][:5]}·{parts[-1]}")
        elif r["job"]:
            parts = r["job"].rsplit("-", 1)
            texts.append(f"{parts[0][:6]}-{parts[-1]}" if len(parts) == 2 else parts[0][:8])
        else:
            texts.append("")
        pod = r["pod"] or {}
        h = f"<b>Worker {r['node']} · GPU slot {r['slot']}</b><br>{LABELS[r['cat']]}"
        if r["job"]:
            h += f"<br>Job/pod: {r['job']}"
        if pod:
            h += f"<br>app: {pod.get('app')}<br>serving: {pod.get('curr_job')}<br>live_time: {pod.get('live_time')} s · reuse count: {pod.get('cache_times')}"
        hovers.append(h)
        custom.append([r["node"], r["job"]])
        lines.append("#F8FAFC" if highlight_job and r["job"] == highlight_job else "#0F172A")
    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="markers+text", text=texts, textposition="middle center",
        textfont=dict(size=9, color="#0B1220"),
        marker=dict(symbol="square", size=46, color=colors, line=dict(width=2, color=lines)),
        hovertext=hovers, hoverinfo="text", customdata=custom,
    ))
    for col, title in ((0, f"Workers 0–{half - 1} · nominal TRAINING cluster"),
                       (1, f"Workers {half}–{num_nodes - 1} · nominal INFERENCE cluster")):
        fig.add_annotation(x=col * (gpus_per_node + 1.6) + (gpus_per_node - 1) / 2, y=0.85, text=title,
                           showarrow=False, font=dict(size=12, color=COLORS["muted"]))
        for i in range(half):
            n = i + col * half
            fig.add_annotation(x=col * (gpus_per_node + 1.6) - 0.85, y=-i, text=f"w{n}", showarrow=False,
                               font=dict(size=11, color=COLORS["muted"]))
    fig.update_xaxes(visible=False, range=[-1.3, 2 * gpus_per_node + 1.2])
    fig.update_yaxes(visible=False, range=[-half + 0.4, 1.2])
    fig.update_layout(height=60 * half + 80, showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
                      plot_bgcolor="rgba(0,0,0,0)", dragmode=False)
    return fig


def node_counts(snapshot: dict, num_nodes: int, gpus_per_node: int) -> Dict[int, Dict[str, int]]:
    out = {n: {k: 0 for k in ["idle"] + ORDER} for n in range(num_nodes)}
    for r in slot_table(snapshot, num_nodes, gpus_per_node):
        if r["slot"] < gpus_per_node:
            out[r["node"]][r["cat"]] += 1
    return out
