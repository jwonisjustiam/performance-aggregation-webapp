#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then echo ".venv가 없습니다. setup_macos.sh를 먼저 실행하세요." >&2; exit 1; fi
"$ROOT/.venv/bin/python" -m streamlit run "$ROOT/app.py"

