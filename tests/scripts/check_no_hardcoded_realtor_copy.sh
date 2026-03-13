#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

declare -a CHECKS=(
  "services/agent-core/app/graph/nodes.py::Te comparto 4 opciones"
  "services/agent-core/app/graph/nodes.py::habitaciones, presupuesto y banos"
  "services/agent-core/app/graph/nodes.py::zona indicada"
  "services/agent-core/app/graph/nodes.py::seleccion inicial"
  "services/agent-core/app/core/prompt_service.py::realtor_guidance"
  "services/agent-core/app/core/prompt_service.py::Regla realtor: usa un tono proactivo"
  "services/agent-core/app/core/prompt_service.py::habitaciones, presupuesto y banos"
)

had_error=0

for rule in "${CHECKS[@]}"; do
  file="${rule%%::*}"
  pattern="${rule#*::}"
  if rg -n --fixed-strings -- "${pattern}" "${file}" > /tmp/no_hardcode_match.txt; then
    echo "Forbidden hardcoded pattern found: ${pattern}"
    cat /tmp/no_hardcode_match.txt
    had_error=1
  fi
done

rm -f /tmp/no_hardcode_match.txt

if [[ "${had_error}" -ne 0 ]]; then
  echo "Hardcode guard failed."
  exit 1
fi

echo "Hardcode guard passed."
