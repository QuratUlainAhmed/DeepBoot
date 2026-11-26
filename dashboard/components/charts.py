"""Plotly chart builders. All inputs are real simulator/experiment data frames."""
from __future__ import annotations

import numpy as np
import pandas
import plotly.graph_objects as go

from .theme import COLORS, LABELS


def gpu_util_figure(series: pandas.DataFrame, total_gpus: int, title: str = "", max_points: int = 4000) -> go.Figure:
    df = series
    if len(df) > max_points:  # thin for rendering only; every k-th 1-s sample, values unchanged
        df = df.iloc[:: int(np.ceil(len(df) / max_points))]
    fig = go.Figure()
    for col, name in (("gpu_use", "Allocated (gpu_use)"), ("real_gpu_use", "Real (excl. rescaling)"),
                      ("real_running_gpu_use", "Real running")):
        fig.add_trace(go.Scatter(x=df["clock"] / 3600, y=100 * df[col] / total_gpus, name=name, mode="lines",
                                 line=dict(width=1.4)))
    fig.update_layout(title=title, xaxis_title="Simulated time (h)", yaxis_title="% of modelled GPUs",
                      yaxis_range=[0, 105], legend=dict(orientation="h", y=-0.25), height=340)
    return fig


def allocation_area(alloc: pandas.DataFrame, total_gpus: int) -> go.Figure:
    fig = go.Figure()
    for col in ["training", "training_rescaling", "inference_running", "inference_protect", "inference_sleep"]:
        if col in alloc:
            fig.add_trace(go.Scatter(x=alloc["clock"] / 60, y=alloc[col], name=LABELS[col], mode="lines",
                                     stackgroup="one", line=dict(width=0.5, color=COLORS[col], shape="hv")))
    fig.update_layout(xaxis_title="Simulated time (min) · sampled at each scheduling step",
                      yaxis_title="GPUs", yaxis_range=[0, total_gpus], height=340,
                      legend=dict(orientation="h", y=-0.3))
    return fig


def cdf_figure(groups: dict, xlabel: str, log_x: bool = False) -> go.Figure:
    fig = go.Figure()
    for name, vals in groups.items():
        v = np.sort(np.asarray(vals, float))
        if len(v) == 0:
            continue
        fig.add_trace(go.Scatter(x=v, y=np.arange(1, len(v) + 1) / len(v), name=name, mode="lines",
                                 line=dict(shape="hv", width=1.6)))
    fig.update_layout(xaxis_title=xlabel, yaxis_title="CDF", height=340, legend=dict(orientation="h", y=-0.3))
    if log_x:
        fig.update_xaxes(type="log")
    return fig


def bar_compare(df: pandas.DataFrame, x: str, y: str, color: str = None, title: str = "", ylab: str = "") -> go.Figure:
    fig = go.Figure()
    if color:
        for i, (k, g) in enumerate(df.groupby(color, sort=False)):
            fig.add_trace(go.Bar(x=g[x], y=g[y], name=str(k)))
        fig.update_layout(barmode="group")
    else:
        fig.add_trace(go.Bar(x=df[x], y=df[y], marker_color=COLORS["repo"]))
    fig.update_layout(title=title, yaxis_title=ylab, height=360, legend=dict(orientation="h", y=-0.25))
    return fig


def event_timeline(events: pandas.DataFrame) -> go.Figure:
    fig = go.Figure()
    for i, (t, g) in enumerate(events.groupby("type")):
        fig.add_trace(go.Scatter(x=g["clock"], y=[t] * len(g), mode="markers", name=t,
                                 marker=dict(size=7, symbol="line-ns-open" if len(g) > 200 else "circle"),
                                 hovertext=g["job"] + ": " + g["detail"], hoverinfo="text"))
    fig.update_layout(xaxis_title="Simulated time (s)", height=360, showlegend=False)
    return fig
