"""Shared colours, CSS and Plotly styling for a consistent dark technical UI."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

COLORS = {
    "idle": "#1E293B",
    "training": "#3B82F6",
    "training_rescaling": "#93C5FD",
    "inference_running": "#F59E0B",
    "inference_protect": "#A855F7",
    "inference_sleep": "#475569",
    "paper": "#94A3B8",
    "repo": "#22D3EE",
    "prototype": "#34D399",
    "grid": "#334155",
    "text": "#E2E8F0",
    "muted": "#94A3B8",
}
LABELS = {
    "idle": "Idle",
    "training": "Training",
    "training_rescaling": "Training (rescale delay)",
    "inference_running": "Inference RUNNING",
    "inference_protect": "Inference PROTECT (warm, reserved)",
    "inference_sleep": "Inference SLEEP (warm, reclaimable)",
}
SERIES = ["#3B82F6", "#22D3EE", "#F59E0B", "#A855F7", "#34D399", "#F472B6", "#FB7185", "#FACC15", "#94A3B8"]

_tpl = go.layout.Template(pio.templates["plotly_dark"])
_tpl.layout.paper_bgcolor = "rgba(0,0,0,0)"
_tpl.layout.plot_bgcolor = "rgba(15,23,42,0.6)"
_tpl.layout.font = dict(family="Inter, Segoe UI, sans-serif", color=COLORS["text"], size=12)
_tpl.layout.colorway = SERIES
_tpl.layout.xaxis = dict(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"])
_tpl.layout.yaxis = dict(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"])
_tpl.layout.margin = dict(l=10, r=10, t=40, b=10)
pio.templates["deepboot"] = _tpl
pio.templates.default = "deepboot"

CSS = """
<style>
.block-container {padding-top: 1.6rem; max-width: 1500px;}
h1, h2, h3 {letter-spacing: -0.01em;}
.db-badge {display:inline-block; padding:2px 8px; border-radius:999px; font-size:0.75rem;
  font-weight:600; margin-right:6px; border:1px solid rgba(148,163,184,.35);}
.db-paper {background:rgba(148,163,184,.15); color:#CBD5E1;}
.db-repo {background:rgba(34,211,238,.12); color:#67E8F9;}
.db-proto {background:rgba(52,211,153,.12); color:#6EE7B7;}
.db-paperonly {background:rgba(244,114,182,.12); color:#F9A8D4;}
.db-card {border:1px solid #334155; border-radius:10px; padding:12px 14px; background:rgba(15,23,42,.55); margin-bottom:10px;}
.db-legend span {display:inline-flex; align-items:center; margin-right:14px; font-size:0.82rem; color:#CBD5E1;}
.db-legend i {width:12px; height:12px; border-radius:3px; margin-right:6px; display:inline-block;}
.db-mono {font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:0.8rem; color:#CBD5E1;}
div[data-testid="stMetricValue"] {font-size:1.5rem;}
</style>
"""


def apply() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def badge(kind: str) -> str:
    text = {"paper": "Paper (approx.)", "repo": "Repository experiment", "proto": "Prototype run",
            "paperonly": "Paper-described, not implemented"}[kind]
    return f'<span class="db-badge db-{kind}">{text}</span>'


def legend_html() -> str:
    items = "".join(f'<span><i style="background:{COLORS[k]}"></i>{v}</span>' for k, v in LABELS.items())
    return f'<div class="db-legend">{items}</div>'
