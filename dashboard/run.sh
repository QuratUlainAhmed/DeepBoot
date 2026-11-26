#!/usr/bin/env bash
# Launch the DeepBoot Interactive Scheduling Simulator.
# Uses the separate `deepboot-dash` conda env; the research `pollux` env is untouched.
set -euo pipefail
cd "$(dirname "$0")/.."            # repository root: the research modules are imported from here
PY="${DEEPBOOT_DASH_PYTHON:-$HOME/miniforge3/envs/deepboot-dash/bin/python}"
export STREAMLIT_THEME_BASE=dark
export STREAMLIT_THEME_PRIMARY_COLOR="#3B82F6"
export STREAMLIT_THEME_BACKGROUND_COLOR="#0B1220"
export STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR="#111A2E"
export STREAMLIT_THEME_TEXT_COLOR="#E2E8F0"
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export PYTHONDONTWRITEBYTECODE=1   # do not rewrite the committed research __pycache__/*.pyc
exec "$PY" -m streamlit run dashboard/app.py "$@"
