import os
import re
from typing import List, Any, Dict
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from pgvector.psycopg2 import register_vector


class VectorRepository:
    def __init__(self):
        self.conn_url = os.getenv("DATABASE_URL")
        raw_table_name = os.getenv("TABLE_VECTORS", "ai_vectors")
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", raw_table_name):
            raise ValueError(f"Invalid TABLE_VECTORS value: {raw_table_name}")
        self.table_name = raw_table_name
        self._initialized = False

    def _get_connection(self):
        conn = psycopg2.connect(self.conn_url)
        register_vector(conn)  # Registra el tipo vector en la conexión
        return conn

    def _ensure_initialized(self):
        if self._initialized:
            return
        self._init_db()
        self._initialized = True

    def _init_db(self):
        """
        Inicializa la tabla de vectores si no existe.
        """
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id SERIAL PRIMARY KEY,
            content_id TEXT NOT NULL,
            client_id TEXT NOT NULL,
            title TEXT,
            body_content TEXT,
            metadata JSONB,
            
            -- Control de idempotencia / versionado
            hash TEXT UNIQUE,

            -- Vector embedding
            -- 3072: Gemini (gemini-embedding-001)
            embedding halfvec(3072),

            -- Auditoría
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS {self.table_name}_embedding_idx
        ON {self.table_name}
        USING hnsw (embedding halfvec_cosine_ops);

        CREATE INDEX IF NOT EXISTS {self.table_name}_client_idx
        ON {self.table_name} (client_id);
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                conn.commit()

    def ping(self) -> bool:
        self._ensure_initialized()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone()[0] == 1

    def search_similar(
        self, 
        client_id: str, 
        query_vector: List[float], 
        top_k: int = 5,
        filters: Dict[str, Any] = None,
        similarity_threshold: float = 0.0
    ):
        """
        Busca documentos similares usando lógica Híbrida:
        - Coincidencia Privada: client_id matches
        - Coincidencia Pública: access_level = 'public'
        
        Usa Named Placeholders (%(name)s) para evitar errores de conteo de parámetros.
        """
        self._ensure_initialized()
        filters = filters or {}
        category = filters.get('category')
        
        # SQL con Named Placeholders
        query = f"""
        SELECT 
            content_id, 
            title, 
            body_content, 
            metadata, 
            1 - (embedding <=> %(vector)s::halfvec) AS similarity
        FROM {self.table_name}
        WHERE 
            (client_id = %(client_id)s OR metadata->>'access_level' IN ('public', 'shared'))
            AND
            (%(category)s::text IS NULL OR metadata->>'category' = %(category)s)
            AND
            (1 - (embedding <=> %(vector)s::halfvec)) > %(threshold)s
        ORDER BY similarity DESC
        LIMIT %(limit)s;
        """
        
        params = {
            "vector": query_vector,
            "client_id": client_id,
            "category": category,
            "threshold": similarity_threshold,
            "limit": top_k
        }

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchall()
