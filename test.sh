#!/usr/bin/env bash
# Alle Prüfungen: ruff (Python 3.11-Syntax) und Tests im Build-Container.
set -euo pipefail
cd "$(dirname "$0")"

.venv/bin/ruff check .
scripts/in-container.sh tests/build/test_check_elf.sh
