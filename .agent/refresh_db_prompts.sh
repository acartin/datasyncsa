#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${OUT_DIR:-.agent}"
OUT_FILE="${OUT_FILE:-$OUT_DIR/ACTIVE_DB_PROMPTS.md}"
PROMPT_ID="${REALTOR_SCORING_PROMPT_ID:-190dc860-9d37-4883-a6f4-c3019fdd882e}"

if [[ ! -f .env ]]; then
  echo "Error: falta '.env' para cargar variables de BD." >&2
  exit 1
fi

set -a
source .env
set +a

for required_var in DB_USER DB_NAME DATABASE_URL; do
  if [[ -z "${!required_var:-}" ]]; then
    echo "Error: variable critica faltante: ${required_var}" >&2
    exit 1
  fi
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: 'docker' es requerido para leer prompts desde Postgres." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

meta_file="$tmp_dir/meta.tsv"
prompt_file="$tmp_dir/prompt.txt"
schema_file="$tmp_dir/schema.json"

docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -At -F '|' -c "
select
  p.id,
  p.version,
  p.is_active,
  p.updated_at::text,
  m.id,
  m.name,
  m.version,
  m.prompt_version,
  coalesce(m.business_domain, ''),
  v.id,
  v.name
from lead_scoring_prompts p
join lead_scoring_models m on m.id = p.model_id
join lead_client_verticals v on v.id = m.vertical_id
where p.id = '$PROMPT_ID';
" > "$meta_file"

if [[ ! -s "$meta_file" ]]; then
  echo "Error: no existe fila en lead_scoring_prompts para id=$PROMPT_ID" >&2
  exit 1
fi

docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -At -c "
select prompt_template
from lead_scoring_prompts
where id = '$PROMPT_ID';
" > "$prompt_file"

docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -At -c "
select jsonb_pretty(extraction_schema)
from lead_scoring_prompts
where id = '$PROMPT_ID';
" > "$schema_file"

IFS='|' read -r prompt_id prompt_version is_active updated_at model_id model_name model_version model_prompt_version business_domain vertical_id vertical_name < "$meta_file"

if [[ -z "$business_domain" ]]; then
  business_domain="(null)"
fi

generated_utc="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

mkdir -p "$OUT_DIR"

{
  echo "# Active DB Prompts"
  echo
  echo "- Generated UTC: \`$generated_utc\`"
  echo "- Source: \`postgres.public.lead_scoring_prompts\`"
  echo "- Refresh command: \`bash .agent/refresh_db_prompts.sh\`"
  echo "- Cache policy: usar este snapshot en bootstrap y refrescarlo una vez por sesion cuando la tarea toque realtor, scoring, lead capture o phrasing conversacional."
  echo
  echo "## Uso obligatorio"
  echo
  echo "- Leer este archivo en el bootstrap de cada sesion junto con \`.agent/RULES.md\` y \`.agent/PY_EXECUTION_MAP.md\`."
  echo "- Para tareas en \`realtor\`, lead capture, scoring, \`slot_hints\`, appointment intent/type o cambios de policy conversacional, refrescar primero desde BD."
  echo "- Si el refresh falla pero este archivo existe, usarlo como snapshot cacheado y reportar la falta de verificacion de frescura."
  echo "- Si este archivo no existe y tampoco se pudo leer la BD, no avanzar con cambios de phrasing o politica conversacional."
  echo
  echo "## Realtor Scoring Prompt V4"
  echo
  echo "- prompt_id: \`$prompt_id\`"
  echo "- prompt_version: \`$prompt_version\`"
  echo "- is_active: \`$is_active\`"
  echo "- updated_at: \`$updated_at\`"
  echo "- model_id: \`$model_id\`"
  echo "- model_name: \`$model_name\`"
  echo "- model_version: \`$model_version\`"
  echo "- model_prompt_version: \`$model_prompt_version\`"
  echo "- vertical_id: \`$vertical_id\`"
  echo "- vertical_name: \`$vertical_name\`"
  echo "- business_domain: \`$business_domain\`"
  echo
  echo "### Query canonica"
  echo
  echo '```sql'
  echo "select p.id, p.version, p.is_active, p.updated_at,"
  echo "       m.id as model_id, m.name as model_name, m.version as model_version, m.prompt_version as model_prompt_version,"
  echo "       v.id as vertical_id, v.name as vertical_name,"
  echo "       p.prompt_template, p.extraction_schema"
  echo "from lead_scoring_prompts p"
  echo "join lead_scoring_models m on m.id = p.model_id"
  echo "join lead_client_verticals v on v.id = m.vertical_id"
  echo "where p.id = '$PROMPT_ID';"
  echo '```'
  echo
  echo "### prompt_template"
  echo
  echo '```text'
  cat "$prompt_file"
  echo '```'
  echo
  echo "### extraction_schema"
  echo
  echo '```json'
  cat "$schema_file"
  echo '```'
} > "$OUT_FILE"

echo "OK: snapshot de prompts DB generado en '$OUT_FILE'"
