#!/usr/bin/env bash
set -euo pipefail


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
  local compose_file="${1:-docker-compose.yml}"

  if [[ ! -f "$compose_file" ]]; then
    return 0
  fi

  if command -v docker >/dev/null 2>&1; then
    if docker compose -f "$compose_file" config --services >/dev/null 2>&1; then
      docker compose -f "$compose_file" config --services
      return 0
    fi
  fi

  awk '
    /^services:/ { in_services=1; next }
    /^[a-zA-Z0-9._-]+:/ { if ($0 !~ /^services:/) in_services=0 }
    in_services && $0 ~ /^  [a-zA-Z0-9._-]+:$/ {
      gsub(":", "", $1)
      print $1
    }
  ' "$compose_file"
}

tree_if_exists() {
  local path="$1"
  if [[ -d "$path" ]]; then
    find "$path" -maxdepth 3 \
      \( -path '*/__pycache__' -o -path '*/output' -o -path '*/output/*' -o -path '*/.next' -o -path '*/node_modules' \) -prune \
      -o -type d -print | sort | sed 's|^\./||'
  fi
}

files_if_exists() {
  local path="$1"
  if [[ -d "$path" ]]; then
    find "$path" -maxdepth 3 \
      \( -path '*/__pycache__' -o -path '*/output' -o -path '*/output/*' -o -path '*/.next' -o -path '*/node_modules' -o -name '*.pyc' \) -prune \
      -o -type f -print | sort | sed 's|^\./||' | head -n 240
  fi
}

cat > "$BRAIN_FILE" <<EOF
# BRAIN_MAP

- Generated UTC: \`$now_utc\`
- Repo root: \`$repo_root\`
- Git branch: \`$branch\`
- Git commit: \`$commit\`

## 1. MAPA DE INTENCIONES (MARKET WATCH)

| Carpeta | Responsabilidad Tecnica | Importancia (1-5) |
|---|---|---:|
| \`docker-compose.yml\` | Compose heredado/actual del repo; revisar antes de tocar infraestructura. | 4 |
| \`services/dagster\` | Orquestacion de Market Watch: assets, jobs, schedules y sensores para coordinar ETL. | 4 |
| \`services/price-scrapper\` | Bounded context de scraping, ETL, campañas, facts y queries base. | 5 |
| \`services/market-watch-api\` | API de producto: auth/multitenancy, datasets livianos, control de \`client_id\`. | 5 |
| \`services/proxy-residencial\` | Proxy residencial BrightData para rotacion de IP en scrappers. | 4 |
| \`services/web/market-watch\` | Frontend cliente: SEO, dashboards, tablas, pivots y reportes. | 5 |
| \`.agent\` | Reglas operativas para agentes en el repo recortado. | 4 |

## 2. LIMITES DE ARQUITECTURA

- \`price-scrapper\` no aloja el producto cliente final.
- \`dagster\` orquesta ETL/assets; no aloja portal cliente ni duplica scraping pesado.
- \`market-watch-api\` no ejecuta scraping ni ETL pesado durante requests web.
- \`web/market-watch\` no se conecta directo a Postgres.
- No reutilizar \`services/web/admin-console\` ni \`services/web/chat-web-renderer\` como base del producto.
- Mantener contratos simples para facilitar separacion futura del repo.

## 3. SERVICIOS DOCKER ACTUALES

\`\`\`text
$(compose_services docker-compose.yml)
\`\`\`

## 4. TOPOLOGIA DE TRABAJO

\`\`\`text
$(tree_if_exists services/price-scrapper)
$(tree_if_exists services/dagster)
$(tree_if_exists services/market-watch-api)
$(tree_if_exists services/proxy-residencial)
$(tree_if_exists services/web/market-watch)
\`\`\`

## 5. ARCHIVOS RELEVANTES

\`\`\`text
$(files_if_exists services/price-scrapper)
$(files_if_exists services/dagster)
$(files_if_exists services/market-watch-api)
$(files_if_exists services/proxy-residencial)
$(files_if_exists services/web/market-watch)
\`\`\`
EOF

append "# AI Context Pack"
append ""
append "- Generated UTC: \`$now_utc\`"
append "- Repo root: \`$repo_root\`"
append "- Git branch: \`$branch\`"
append "- Git commit: \`$commit\`"
append "- Policy: high-signal only; enfocado en Market Watch / pricing."

append_section "Contexto Maestro"
append_file_excerpt "$BRAIN_FILE"

append_section "Reglas Operativas"
append_file_excerpt ".agent/RULES.md"
append_file_excerpt ".agent/PY_EXECUTION_MAP.md"
append_file_excerpt "AGENTS.md"

append_section "Compose y Variables"
append "### Servicios del compose principal"
append ""
append_codeblock text "$(compose_services docker-compose.yml)"
append_range_excerpt "docker-compose.yml" 1 220
append_file_excerpt ".env.example"

append_section "Topologia Market Watch"
append_codeblock text \
"$(tree_if_exists services/price-scrapper)
$(tree_if_exists services/dagster)
$(tree_if_exists services/market-watch-api)
$(tree_if_exists services/proxy-residencial)
$(tree_if_exists services/web/market-watch)"

append_section "Archivos Market Watch"
append_codeblock text \
"$(files_if_exists services/price-scrapper)
$(files_if_exists services/dagster)
$(files_if_exists services/market-watch-api)
$(files_if_exists services/proxy-residencial)
$(files_if_exists services/web/market-watch)"

append_section "Extractos de Servicio"
append_file_excerpt "services/proxy-residencial/brightdata.py"
append_file_excerpt "services/price-scrapper/README.md"
append_file_excerpt "services/price-scrapper/requirements.txt"
append_file_excerpt "services/dagster/README.md"
append_file_excerpt "services/dagster/workspace.yaml"
append_file_excerpt "services/dagster/dagster.yaml"
append_file_excerpt "services/market-watch-api/README.md"
append_file_excerpt "services/web/market-watch/README.md"
append_file_excerpt "services/web/market-watch/package.json"

mv "$tmp_file" "$OUT_FILE"

echo "OK: contexto regenerado en '$BRAIN_FILE' y '$OUT_FILE'"
