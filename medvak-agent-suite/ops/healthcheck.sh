#!/usr/bin/env bash
set -euo pipefail
curl -fsS http://localhost:8000/healthz >/dev/null
