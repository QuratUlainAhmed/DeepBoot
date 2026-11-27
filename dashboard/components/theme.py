"""Shared colours, CSS and Plotly styling for a consistent dark technical UI."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

COLORS = {
    "idle": "#273244",
    "training": "#3B82F6",
    "training_rescaling": "#93C5FD",
    "inference_running": "#F59E0B",
    "inference_protect": "#A855F7",
    "inference_sleep": "#5B6B82",
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
/* ---- status header ---- */
.db-status {display:flex; flex-wrap:wrap; gap:10px 18px; align-items:center; margin:-4px 0 6px 0; color:#94A3B8; font-size:.88rem;}
.db-status b {color:#E2E8F0; font-weight:600;}
.db-pill {padding:3px 10px; border-radius:999px; font-weight:700; font-size:.78rem; letter-spacing:.04em; text-transform:uppercase;}
.db-pill.ready {background:rgba(148,163,184,.18); color:#CBD5E1;}
.db-pill.running {background:rgba(52,211,153,.16); color:#6EE7B7; box-shadow:0 0 0 1px rgba(52,211,153,.35) inset;}
.db-pill.paused {background:rgba(250,204,21,.14); color:#FDE68A;}
.db-pill.completed {background:rgba(59,130,246,.18); color:#93C5FD;}
.db-pill.error {background:rgba(244,63,94,.18); color:#FDA4AF;}
.db-pill.running::before {content:"●  "; animation: db-blink 1.2s infinite;}
@keyframes db-blink {50% {opacity:.25;}}
/* ---- GPU cluster grid ---- */
.db-cluster {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin:4px 0 6px 0;}
@media (max-width: 900px) {.db-cluster {grid-template-columns:repeat(2,minmax(0,1fr));}}
.worker {border:1px solid #243047; border-radius:10px; padding:7px 8px 8px; background:rgba(15,23,42,.65); transition:border-color .4s;}
.worker.busy {border-color:#334155;}
.w-head {display:flex; justify-content:space-between; font-size:.74rem; color:#94A3B8; margin-bottom:5px;}
.w-head b {color:#CBD5E1; font-family:ui-monospace,Menlo,monospace; letter-spacing:.03em;}
.w-slots {display:grid; gap:5px; grid-template-columns:repeat(4,1fr);}
.w-slots.g2 {grid-template-columns:repeat(2,1fr);} .w-slots.g8 {grid-template-columns:repeat(4,1fr);}
.gpu {height:38px; border-radius:6px; display:flex; align-items:center; justify-content:center; overflow:hidden;
  font-size:.66rem; font-family:ui-monospace,Menlo,monospace; color:#0B1220; font-weight:600;
  transition:background-color .6s ease, box-shadow .6s ease; cursor:default; position:relative;}
.gpu span {white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding:0 3px;}
.gpu.idle {background:#273244; box-shadow:inset 0 0 0 1px #334155;}
.gpu.trn {background:#3B82F6;}
.gpu.rsc {background:repeating-linear-gradient(135deg,#93C5FD 0 6px,#60A5FA 6px 12px);}
.gpu.inf {background:#F59E0B;}
.gpu.pro {background:#A855F7; color:#F5F3FF;}
.gpu.slp {background:repeating-linear-gradient(135deg,#5B6B82 0 5px,#4B5A70 5px 10px); color:#E2E8F0;}
.gpu.focus {box-shadow:0 0 0 2px #F8FAFC, 0 0 12px rgba(248,250,252,.35);}
.gpu.chg-in {animation: db-in .9s ease-out 1;}
.gpu.chg-state {animation: db-state 1.1s ease-out 1;}
@keyframes db-in {0% {transform:scale(.55); opacity:.2; filter:brightness(1.8);} 60% {transform:scale(1.06);} 100% {transform:scale(1); opacity:1; filter:none;}}
@keyframes db-state {0%,40% {filter:brightness(1.7) saturate(1.3);} 100% {filter:none;}}
.w-lost {margin-top:5px; font-size:.66rem; color:#FDA4AF; font-family:ui-monospace,Menlo,monospace; animation: db-fade 2.5s ease-out 1 forwards;}
@keyframes db-fade {0% {opacity:1;} 100% {opacity:.55;}}
/* ---- story cards ---- */
.db-story {border:1px solid #334155; border-left:4px solid var(--acc,#3B82F6); border-radius:10px; padding:12px 16px;
  background:rgba(15,23,42,.6); margin-bottom:10px;}
.db-story.main {padding:16px 18px; background:linear-gradient(90deg, rgba(30,41,59,.85), rgba(15,23,42,.6));}
.db-story .tag {font-size:.7rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:var(--acc,#3B82F6);}
.db-story .ttl {font-size:1.02rem; font-weight:600; color:#F1F5F9; margin:2px 0 6px;}
.db-story.main .ttl {font-size:1.2rem;}
.db-story .kv {display:grid; grid-template-columns:max-content 1fr; gap:3px 14px; font-size:.84rem; color:#CBD5E1;}
.db-story .kv i {font-style:normal; color:#94A3B8;}
.db-story .note {font-size:.76rem; color:#94A3B8; margin-top:7px;}
.db-story code, .db-delta code {background:rgba(51,65,85,.6); color:#E2E8F0; padding:0 4px; border-radius:4px; font-size:.78rem;}
.acc-blue {--acc:#3B82F6;} .acc-lblue {--acc:#60A5FA;} .acc-amber {--acc:#F59E0B;} .acc-purple {--acc:#A855F7;}
.acc-cyan {--acc:#22D3EE;} .acc-green {--acc:#34D399;} .acc-grey {--acc:#94A3B8;}
.db-delta {display:flex; flex-wrap:wrap; gap:6px 16px; font-size:.8rem; color:#94A3B8; margin:2px 0 10px;}
.db-delta b {color:#E2E8F0;} .db-delta .it {white-space:nowrap;} .db-delta .up {color:#6EE7B7;} .db-delta .dn {color:#FDA4AF;}
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
