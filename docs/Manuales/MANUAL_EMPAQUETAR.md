# Manual de Usuario: `.agent/regenerar_contexto.sh`

## 1. Propósito

`.agent/regenerar_contexto.sh` regenera el contexto en un solo paso y guarda todo dentro de `.agent`.

Salida por defecto:
- `.agent/BRAIN_MAP.md`
- `.agent/AI_CONTEXT_PACK.md`

## 2. Uso básico

Desde la raíz del repo:

```bash
bash .agent/regenerar_contexto.sh
```

## 3. Parámetros de control

El script usa variables de entorno para ajustar el nivel de detalle del pack:

- `MAX_LINES_PER_FILE`: líneas máximas por archivo incluido.
- `MAX_FILE_SIZE_KB`: tamaño máximo (KB) por archivo para incluirlo.

Ejemplo compacto (menos tokens):

```bash
MAX_LINES_PER_FILE=120 MAX_FILE_SIZE_KB=96 bash .agent/regenerar_contexto.sh
```

Ejemplo profundo (más detalle):

```bash
MAX_LINES_PER_FILE=320 MAX_FILE_SIZE_KB=512 bash .agent/regenerar_contexto.sh
```

## 4. Qué incluye el paquete

El `.md` generado incluye secciones de alto valor:

- Contexto maestro (`BRAIN_MAP.md` si existe).
- Infraestructura (`docker-compose.yml`, `.env.example`, `rclone-mount.service`, provisioning).
- Topología técnica (directorios relevantes).
- Entry points (FastAPI y arranque de servicios).
- Rutas API detectadas (`@router.get/post/...`).
- Contratos/modelos/firma de funciones críticas.
- Mapa de tablas SQL referenciadas.
- Núcleo SUID/SDUI.
- Orquestadores de IA.
- ETL + storage (R2/staging).
- Pruebas clave.
- Deuda técnica detectable (heurística).

## 5. Casos de uso recomendados

1. Snapshot para iniciar una nueva sesión IA (recomendado):
```bash
bash .agent/regenerar_contexto.sh
```

2. Contexto corto para modelos con límite de tokens:
```bash
MAX_LINES_PER_FILE=120 MAX_FILE_SIZE_KB=96 bash .agent/regenerar_contexto.sh
```

3. Contexto para refactor grande:
```bash
MAX_LINES_PER_FILE=320 MAX_FILE_SIZE_KB=512 bash .agent/regenerar_contexto.sh
```

4. Preparar contexto antes de code review:
```bash
bash .agent/regenerar_contexto.sh
```

5. Onboarding rápido de un dev nuevo:
- Compartir `.agent/BRAIN_MAP.md` + `.agent/AI_CONTEXT_PACK.md`.

## 6. Flujo recomendado de trabajo

1. Actualiza tu rama.
2. Ejecuta `.agent/regenerar_contexto.sh`.
3. Revisa que el archivo generado tenga el foco correcto.
4. Pasa ese `.md` a la IA en lugar de pegar carpetas completas.
5. Si falta profundidad, sube `MAX_LINES_PER_FILE`/`MAX_FILE_SIZE_KB` y regenera.

## 7. Troubleshooting

### Error: `rg (ripgrep) es requerido`
Instala `ripgrep`:

```bash
sudo apt-get update && sudo apt-get install -y ripgrep
```

### El contexto quedó demasiado grande
Reduce límites:

```bash
MAX_LINES_PER_FILE=100 MAX_FILE_SIZE_KB=64 bash .agent/regenerar_contexto.sh
```

### Faltó información clave
Aumenta límites:

```bash
MAX_LINES_PER_FILE=400 MAX_FILE_SIZE_KB=768 bash .agent/regenerar_contexto.sh
```

### `BRAIN_MAP.md` no aparece
Ejecuta el flujo unificado:

```bash
bash .agent/regenerar_contexto.sh
```

## 8. Notas operativas

- El script está diseñado para priorizar señales estructurales sobre contenido bruto.
- No sustituye documentación funcional de producto; optimiza contexto técnico para IA.
- Recomendación: versionar el manual y los archivos de `.agent` junto con cambios arquitectónicos.
