#!/usr/bin/env bash
set -euo pipefail

if ! command -v rg >/dev/null 2>&1; then
  echo "Error: 'rg' (ripgrep) es requerido." >&2
  exit 1
fi

MAX_LINES_PER_FILE="${MAX_LINES_PER_FILE:-180}"
MAX_FILE_SIZE_KB="${MAX_FILE_SIZE_KB:-256}"

OUT_DIR=".agent"
BRAIN_FILE="$OUT_DIR/BRAIN_MAP.md"
OUT_FILE="$OUT_DIR/AI_CONTEXT_PACK.md"

mkdir -p "$OUT_DIR"

repo_root="$(pwd)"
now_utc="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")"
commit="$(git rev-parse --short HEAD 2>/dev/null || echo "N/A")"

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

append() {
  printf "%s\n" "$*" >> "$tmp_file"
}

append_section() {
  append ""
  append "## $1"
  append ""
}

append_codeblock() {
  local lang="$1"
  shift
  append '```'"$lang"
  printf "%s\n" "$@" >> "$tmp_file"
  append '```'
}

append_file_excerpt() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 0
  fi

  local size_kb
  size_kb="$(du -k "$file" | cut -f1)"
  if (( size_kb > MAX_FILE_SIZE_KB )); then
    append "- \`$file\` (omitido: ${size_kb}KB > ${MAX_FILE_SIZE_KB}KB)"
    return 0
  fi

  append "### \`$file\`"
  append ""
  append '```'
  sed -n "1,${MAX_LINES_PER_FILE}p" "$file" >> "$tmp_file"
  append '```'
}

append_range_excerpt() {
  local file="$1"
  local start="$2"
  local end="$3"

  if [[ ! -f "$file" ]]; then
    return 0
  fi

  append "### \`$file:$start-$end\`"
  append ""
  append '```'
  sed -n "${start},${end}p" "$file" >> "$tmp_file"
  append '```'
}

compose_services() {
  if command -v docker >/dev/null 2>&1; then
    if docker compose config --services >/dev/null 2>&1; then
      docker compose config --services
      return 0
    fi
  fi

  awk '
    /^services:/ { in_services=1; next }
    /^networks:/ { in_services=0 }
    /^volumes:/ { in_services=0 }
    in_services && $0 ~ /^  [a-zA-Z0-9._-]+:$/ {
      gsub(":", "", $1)
      print $1
    }
  ' docker-compose.yml
}

active_entrypoints() {
  rg -n --no-heading 'FastAPI\(|app\.include_router|if __name__ == "__main__"|uvicorn\.run\(' \
    services/ai_runtime \
    services/scoring-core \
    services/web/chat-web-renderer/backend \
    services/web/admin-console/backend \
    services/etl-docs \
    -g '*.py' \
    | sed 's|^\./||'
}

active_routes() {
  rg -n --no-heading '^@router\.(get|post|put|patch|delete)\(|^@app\.(get|post|put|patch|delete)\(' \
    services/ai_runtime \
    services/scoring-core \
    services/web/chat-web-renderer/backend \
    services/web/admin-console/backend \
    services/etl-docs \
    -g '*.py' \
    | sed 's|^\./||'
}

cat > "$BRAIN_FILE" <<EOF
# BRAIN_MAP

- Generated UTC: \`$now_utc\`
- Repo root: \`$repo_root\`
- Git branch: \`$branch\`
- Git commit: \`$commit\`

## 1. MAPA DE INTENCIONES (STACK ACTUAL)

| Carpeta | Responsabilidad Tecnica | Importancia (1-5) |
|---|---|---:|
| \`docker-compose.yml\` | Orquestacion oficial del stack local. | 5 |
| \`services/ai_runtime\` | Runtime conversacional LangGraph multitenant; autoridad principal de chat. | 5 |
| \`services/scoring-core\` | Dominio separado de scoring asincrono con API y worker propios. | 5 |
| \`services/web/chat-web-renderer\` | Canal web y renderer SDUI que consume \`ai-runtime\`. | 5 |
| \`services/web/admin-console\` | Consola operativa multi-tenant. | 4 |
| \`services/etl-docs\` | ETL documental, vectorizacion y reseteo de memoria best-effort. | 4 |
| \`services/data\` | Repositorios y caches compartidos del runtime conversacional. | 5 |
| \`schemas\` | Contratos compartidos entre servicios. | 4 |
| \`tests\` | Pruebas cross-service, smoke y sandboxes. | 4 |

## 2. ZONAS NO AUTORITATIVAS

| Carpeta | Estado |
|---|---|
| \`services/etl-processor\` | Deprecado. |
| \`services/ai-agents\` | Exploracion; no participa en el runtime operativo. |

## 3. ARQUITECTURA CORE

- \`ai-runtime\` resuelve tenant, vertical, flow y estado de sesion.
- \`realtor_flow\` y \`basic_flow\` son selectores logicos internos.
- \`analyze_turn\` e \`intent_detector\` son prompts semanticos por vertical; \`shared\` solo debe contener piezas tecnicas neutrales.
- \`scoring-core\` permanece separado y no debe absorber decisiones conversacionales.
- \`chat-web-renderer\` es consumidor/canal, no autoridad de negocio.
- Toda operacion conversacional debe mantener scope por \`client_id\`.

## 4. SERVICIOS DOCKER ACTIVOS

\`\`\`text
$(compose_services)
\`\`\`

## 5. ENTRY POINTS PRINCIPALES

- \`services/ai_runtime/main.py\`
- \`services/scoring-core/main.py\`
- \`services/web/chat-web-renderer/backend/app/main.py\`
- \`services/web/admin-console/backend/app/main.py\`
- \`services/etl-docs/main.py\`

## 6. REFERENCIAS CANONICAS

- \`services/ai_runtime/ARCHITECTURE.md\`
- \`.agent/RULES.md\`
- \`.agent/PY_EXECUTION_MAP.md\`

## 7. ENTIDADES Y CAPAS CRITICAS

- Tenancy/runtime: \`client_id\`, \`tenant_config\`, \`session_id\`, \`conversation_id\`
- Estado conversacional: \`services/ai_runtime/domain/state.py\`
- Datos compartidos: \`services/data/cache/**\`, \`services/data/repositories/**\`
- Scoring: \`lead_scorecards\`, \`lead_score_items\`, \`lead_scoring_models\`, \`lead_scoring_prompts\`
- RAG: FAQ por tenant y documentos por tenant en Postgres/pgvector
EOF

append "# AI Context Pack"
append ""
append "- Generated UTC: \`$now_utc\`"
append "- Repo root: \`$repo_root\`"
append "- Git branch: \`$branch\`"
append "- Git commit: \`$commit\`"
append "- Policy: high-signal only; enfocado en stack actual."

append_section "Contexto Maestro"
append_file_excerpt "$BRAIN_FILE"

append_section "Compose y Variables"
append "### Servicios activos del compose"
append ""
append_codeblock text "$(compose_services)"
append_range_excerpt "docker-compose.yml" 1 220
append_range_excerpt "docker-compose.yml" 300 360
append_range_excerpt ".env.example" 50 120

append_section "Topologia Relevante"
append_codeblock text \
"$(find services/ai_runtime services/scoring-core services/data services/web/chat-web-renderer services/web/admin-console services/etl-docs schemas tests -maxdepth 3 -type d 2>/dev/null | sort | sed 's|^\./||')"

append_section "Entry Points Detectados"
append_codeblock text "$(active_entrypoints)"

append_section "Rutas API Detectadas"
append_codeblock text "$(active_routes)"

append_section "AI Runtime"
append_file_excerpt ".agent/AI_RUNTIME_BOOTSTRAP.md"
append_file_excerpt "docs/AI_RUNTIME_PROMPT_RUNTIME.md"
append_file_excerpt "services/ai_runtime/ARCHITECTURE.md"
append_file_excerpt "services/ai_runtime/main.py"
append_file_excerpt "services/ai_runtime/api.py"
append_file_excerpt "services/ai_runtime/runtime/settings.py"
append_file_excerpt "services/ai_runtime/runtime/bootstrap.py"
append_file_excerpt "services/ai_runtime/runtime/service.py"
append_file_excerpt "services/ai_runtime/domain/state.py"
append_file_excerpt "services/ai_runtime/graph/registry.py"
append_file_excerpt "services/ai_runtime/graph/generic/graph.py"
append_file_excerpt "services/ai_runtime/graph/realtor/graph.py"

append_section "Canal Web"
append_file_excerpt "services/web/chat-web-renderer/backend/app/core/runtime_client.py"
append_file_excerpt "services/web/chat-web-renderer/backend/app/core/memory_reset.py"
append_file_excerpt "services/web/chat-web-renderer/backend/app/main.py"

append_section "Data Layer Compartida"
append_file_excerpt "services/data/repositories/base.py"
append_file_excerpt "services/data/cache/session_store.py"
append_file_excerpt "services/ai_runtime/config/tenant_loader.py"
append_file_excerpt "services/ai_runtime/config/prompt_composer.py"

append_section "Scoring Boundary"
append_file_excerpt "services/scoring-core/README.md"
append_file_excerpt "services/scoring-core/main.py"
append_file_excerpt "services/scoring-core/worker.py"

append_section "Pruebas y Sandboxes"
append_codeblock text \
"$(find tests -maxdepth 3 -type f 2>/dev/null | sort | sed 's|^\./||' | sed -n '1,400p')"

mv "$tmp_file" "$OUT_FILE"

echo "OK: BRAIN_MAP generado en '$BRAIN_FILE'"
echo "OK: AI context pack generado en '$OUT_FILE' ($(du -h "$OUT_FILE" | cut -f1))"
echo "Tip: MAX_LINES_PER_FILE=$MAX_LINES_PER_FILE MAX_FILE_SIZE_KB=$MAX_FILE_SIZE_KB"
