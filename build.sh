#!/usr/bin/env bash
# Baut das Addon-Zip für Raspberry Pi 5 / LibreELEC 12 / Kodi 21 im Docker-Container.
set -euo pipefail
cd "$(dirname "$0")"

scripts/in-container.sh scripts/build-in-container.sh
