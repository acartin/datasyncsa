#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Regeneración de contexto en un paso (solo .agent):
# - .agent/BRAIN_MAP.md
# - .agent/AI_CONTEXT_PACK.md
# ------------------------------------------------------------

if ! command -v rg >/dev/null 2>&1; then
  echo "Error: 'rg' (ripgrep) es requerido." >&2
  exit 1
fi

MAX_LINES_PER_FILE="${MAX_LINES_PER_FILE:-220}"
MAX_FILE_SIZE_KB="${MAX_FILE_SIZE_KB:-256}"

OUT_DIR=".agent"
BRAIN_FILE="$OUT_DIR/BRAIN_MAP.md"
OUT_FILE="$OUT_DIR/AI_CONTEXT_PACK.md"

mkdir -p "$OUT_DIR"

repo_root="$(pwd)"
now_utc="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")"
commit="$(git rev-parse --short HEAD 2>/dev/null || echo "N/A")"

cat > "$BRAIN_FILE" <<EOF
# BRAIN_MAP

- Generated UTC: \`$now_utc\`
- Repo root: \`$repo_root\`
- Git branch: \`$branch\`
- Git commit: \`$commit\`

## 1. MAPA DE INTENCIONES (DIRECTORIO)

| Carpeta | Responsabilidad Técnica | Importancia (1-5) |
|---|---|---:|
| \`docker-compose.yml\` | Orquestación de servicios (DB, Redis, APIs, bridges, UI, ETL). | 5 |
| \`services/web/admin-console\` | BFF FastAPI + renderer SDUI para consola operativa multi-tenant. | 5 |
| \`services/web/realtor-chat\` | Bridge y widget chat SDUI inmobiliario. | 5 |
| \`services/inference-stack-v2/inference-core-v2\` | Motor v2 de chat/scoring por vertical/modelo/prompt. | 5 |
| \`services/inference-stack-v2/semantic-adapter-v2\` | Recuperación semántica v2 (RAG retriever). | 5 |
| \`services/etl-docs\` | Ingesta documental, colas RQ y vectorización. | 5 |
| \`schemas\` | Contratos canónicos compartidos entre servicios. | 4 |
| \`tests\` | Pruebas de integración y sistema cross-service. | 4 |
| \`volumes/r2_storage\` | Storage documental montado (Cloudflare R2 vía rclone). | 5 |
| \`volumes/staging\` | Buffer de staging para pipelines ETL. | 4 |
| \`services/etl-processor\` | Servicio deprecado (no usar para features nuevas). | 1 |
| \`services/legacy-ETL_DOCS\` | Código ETL legacy/deprecado. | 1 |

## 2. ARQUITECTURA CORE (SDUI/SUID)

- Backend soberano: frontend renderiza contratos SDUI, no decide negocio.
- Multi-tenant estricto: toda consulta operativa debe tener scope por \`client_id\`.
- Contratos UI validados con Pydantic y consistentes con renderer.

## 3. ENTRY POINTS PRINCIPALES

- \`services/web/admin-console/backend/app/main.py\`
- \`services/web/realtor-chat/backend/app/main.py\`
- \`services/inference-stack-v2/inference-core-v2/main.py\`
- \`services/inference-stack-v2/semantic-adapter-v2/main.py\`
- \`services/etl-docs/main.py\`

## 4. ENTIDADES CRÍTICAS (DB)

- Tenancy/seguridad: \`lead_clients\`, \`auth_users\`, \`auth_roles\`, \`auth_client_user\`
- Leads/conversación: \`lead_leads\`, \`lead_conversations\`, \`lead_statuses\`, \`lead_sources\`
- Scoring v2: \`lead_scorecards\`, \`lead_score_items\`, \`lead_scoring_models\`, \`lead_scoring_criteria\`, \`lead_scoring_bands\`, \`lead_scoring_prompts\`
- RAG/documentos: \`ai_knowledge_documents\`, \`ai_vectors\`
EOF

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

append "# AI Context Pack"
append ""
append "- Generated UTC: \`$now_utc\`"
append "- Repo root: \`$repo_root\`"
append "- Git branch: \`$branch\`"
append "- Git commit: \`$commit\`"
append "- Policy: High-signal only; assets/binarios excluidos."

append_section "Contexto Maestro"
append "- Fuente principal: \`$BRAIN_FILE\`"
append_file_excerpt "$BRAIN_FILE"

append_section "Infraestructura y Entradas"
append_file_excerpt "docker-compose.yml"
append_file_excerpt ".env.example"
append_file_excerpt "rclone-mount.service"
append_file_excerpt "docs/SERVER_PROVISIONING.md"

append_section "Topología Técnica (directorios clave)"
append_codeblock text \
"$(find services tests schemas docs -maxdepth 3 -type d 2>/dev/null | sort | sed 's|^\./||')"

append_section "Entry Points Detectados"
append_codeblock text \
"$(rg -n --no-heading 'FastAPI\(|app\.include_router|if __name__ == \"__main__\"|uvicorn\.run\(' \
  services \
  -g '*.py' \
  | sed 's|^\./||' \
  | sed -n '1,400p')"

append_section "Rutas API Detectadas"
append_codeblock text \
"$(rg -n --no-heading '^@router\.(get|post|put|patch|delete)\(' \
  services \
  -g '*.py' \
  | sed 's|^\./||' \
  | sed -n '1,1000p')"

append_section "Contratos/Modelos Críticos"
append_codeblock text \
"$(rg -n --no-heading '^class [A-Za-z_][A-Za-z0-9_]*\((BaseModel|SQLAlchemyBaseUserTableUUID|Base)\)|^(async[[:space:]]+def|def)[[:space:]]+[A-Za-z_][A-Za-z0-9_]*\(' \
  services/web/admin-console/backend/app/contracts \
  services/web/realtor-chat/backend/app/schemas \
  services/inference-stack/inference-core/app/models \
  services/inference-stack-v2/inference-core-v2/app/models \
  services/etl-docs/src/shared \
  -g '*.py' 2>/dev/null \
  | sed 's|^\./||' \
  | sed -n '1,1200p')"

append_section "Tablas/SQL Referenciadas (DB Map)"
append_codeblock text \
"$(rg -n --no-heading -o 'lead_[a-zA-Z0-9_]+|auth_[a-zA-Z0-9_]+|ai_[a-zA-Z0-9_]+' \
  services \
  -g '*.py' \
  | sed 's|^\./||' \
  | awk -F: '{print $1 " -> " $NF}' \
  | sort -u \
  | sed -n '1,2000p')"

append_section "Motor SUID/SDUI (archivos núcleo)"
for f in \
  services/web/admin-console/backend/app/contracts/ui_schema.py \
  services/web/admin-console/backend/app/modules/shared/sdui.py \
  services/web/admin-console/frontend/renderer/main.js \
  services/web/admin-console/frontend/renderer/engine/registry.js \
  services/web/realtor-chat/backend/app/schemas/ui.py \
  services/web/realtor-chat/backend/app/transformer/core.py \
  services/web/realtor-chat/frontend/core/renderer.js \
  services/web/realtor-chat/backend/app/main.py \
  services/web/admin-console/backend/app/main.py
do
  append_file_excerpt "$f"
done

append_section "Inyección IA / Orquestadores"
for f in \
  services/inference-stack/inference-core/app/services/chat_orchestrator.py \
  services/inference-stack/inference-core/app/services/lead_analyzer.py \
  services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py \
  services/inference-stack-v2/inference-core-v2/app/services/scoring_engine.py \
  services/inference-stack-v2/inference-core-v2/app/services/prompt_builder.py \
  services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py \
  services/web/realtor-chat/backend/app/core/inference_bridge.py
do
  append_file_excerpt "$f"
done

append_section "ETL + Storage (R2/Staging)"
for f in \
  services/etl-docs/main.py \
  services/etl-docs/src/shared/file_manager.py \
  services/etl-docs/src/shared/vector_store.py \
  services/etl-docs/src/shared/memory_reset.py \
  services/etl-docs/src/ETL_DOCS/processor.py \
  services/etl-docs/src/ETL_DOCS/worker_task.py
do
  append_file_excerpt "$f"
done

append_section "Pruebas y Diagnóstico"
append_codeblock text \
"$(find tests services -type f 2>/dev/null \
  | rg 'tests/.+\\.(py|md)$' \
  | sed 's|^\./||' \
  | sort \
  | sed -n '1,1200p')"
append_file_excerpt "tests/README.md"
append_file_excerpt "tests/sandbox/simulate_chat_flow.py"

append_section "Deuda Técnica Detectable (heurística)"
append_codeblock text \
"$(printf '%s\n' \
  'services/etl-processor (deprecated placeholder)' \
  'services/legacy-ETL_DOCS (legacy duplicate path)' \
  'services/web/datasyncsa (sitio estático fuera de SUID)' \
  'services/web/tests (UI de pruebas manuales)' \
  'services/web/admin-console/docs + themes (assets plantilla)')"

mv "$tmp_file" "$OUT_FILE"

echo "OK: BRAIN_MAP generado en '$BRAIN_FILE'"
echo "OK: AI context pack generado en '$OUT_FILE' ($(du -h "$OUT_FILE" | cut -f1))"
echo "Tip: MAX_LINES_PER_FILE=$MAX_LINES_PER_FILE MAX_FILE_SIZE_KB=$MAX_FILE_SIZE_KB"
