#!/usr/bin/env bash
# Run mypy against the backend. Currently enforces type-checking on the
# newly-refactored routes/ modules (sitemap, corporate_services, cs_invoices).
# Legacy server.py + business.py get relaxed rules — they'll be tightened as
# they're broken up module-by-module in the ongoing refactor.
#
# Usage:  ./scripts/lint_types.sh                   # check the strict targets
#         ./scripts/lint_types.sh --all             # check everything (verbose)
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--all" ]]; then
  exec mypy --config-file mypy.ini .
fi

exec mypy --config-file mypy.ini \
  routes/sitemap.py \
  routes/corporate_services.py \
  routes/cs_invoices.py \
  routes/players_corp_email.py
