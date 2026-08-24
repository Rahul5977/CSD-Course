#!/usr/bin/env bash
# Cold-start the whole stack in dependency order: state -> backends -> LB.
# Assumes code was already deployed once (deploy.sh all does deploy+start).
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/deploy.sh state
bash scripts/deploy.sh sys2
bash scripts/deploy.sh sys3
bash scripts/deploy.sh sys4
bash scripts/deploy.sh lb
bash scripts/sanity_check.sh
