#!/usr/bin/env bash
# Alle Prüfungen: ruff (Python 3.11-Syntax), Build-Skript-Tests und C++-Tests im Build-Container.
set -euo pipefail
cd "$(dirname "$0")"

.venv/bin/ruff check .
python3 -B -m unittest discover -s tests/python -v
scripts/in-container.sh tests/build/test_check_elf.sh
scripts/in-container.sh tests/build/test_check_zip.sh
scripts/in-container.sh scripts/test-cpp-in-container.sh

# Auch Kodi-/GLES-Anbindung und das tatsächlich ausgelieferte Zip prüfen.
./build.sh
