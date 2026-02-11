# Usamos PostGIS como base (ya trae GEOS, GDAL, PROJ)
FROM postgis/postgis:17-3.5

# Instalamos la extensión de vectores para IA (pgvector)
RUN apt-get update && \
    apt-get install -y postgresql-17-pgvector && \
    rm -rf /var/lib/apt/lists/*
