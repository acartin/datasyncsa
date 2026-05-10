# `mkt_dim_category`

## Qué es
Catálogo simple de categorías raíz por cadena.

Cada fila representa una root category operativa del scraper.

## Qué script correr
No necesita un loader ETL especial para funcionar día a día.

La extracción usa directamente esta tabla desde BD.

## Qué hace
- guarda root categories por `chain`
- conserva `slug`, `name`, `url`
- guarda `source_category_reference` cuando el engine lo necesita
- usa `is_enabled` como switch simple de scraping

## Tipo de actualización
Manual / `update`

La regla operativa es:
- `is_enabled = true`: entra al scrape por defecto
- `is_enabled = false`: no entra al scrape por defecto

## Frecuencia recomendada
Media.

Recomendado:
- cuando cambien categorías raíz
- cuando quieras habilitar o deshabilitar roots de scraping

## Notas
- Ya no mezcla categorías observadas con configuración operativa.
- El ETL de catálogo lee esta tabla directamente.
