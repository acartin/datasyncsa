import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger("database")

class DatabaseManager:
    def __init__(self):
        self.host = os.getenv("DB_HOST", "postgres")
        self.port = int(os.getenv("DB_PORT", "5432"))
        self.database = os.getenv("DB_NAME") or os.getenv("DB_DATABASE", "agentic")
        self.user = os.getenv("DB_USER") or os.getenv("DB_USERNAME", "postgres")
        self.password = os.getenv("DB_PASS") or os.getenv("DB_PASSWORD", "")
        self._conn = None

    def get_connection(self):
        if self._conn is None or self._conn.closed:
            try:
                self._conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    cursor_factory=RealDictCursor
                )
                logger.info("✅ Connected to central database.")
            except Exception as e:
                logger.error(f"❌ Database connection error: {e}")
                return None
        return self._conn

    def get_property(self, property_id):
        conn = self.get_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                # Get property details
                cur.execute("SELECT * FROM lead_properties WHERE id = %s", (property_id,))
                prop = cur.fetchone()
                if not prop: return None
                
                # Get images
                cur.execute("SELECT original_url FROM lead_property_images WHERE property_id = %s ORDER BY sort_order", (property_id,))
                images = cur.fetchall()
                prop['images'] = [img['original_url'] for img in images]
                
                return prop
        except Exception as e:
            logger.error(f"Error fetching property {property_id}: {e}")
            return None

    def get_branding(self, client_id, brand_project=None):
        conn = self.get_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                brand = None
                if brand_project:
                    cur.execute(
                        "SELECT * FROM lead_brand_configs WHERE client_id = %s AND project = %s",
                        (client_id, brand_project),
                    )
                    brand = cur.fetchone()

                if not brand:
                    cur.execute(
                        "SELECT * FROM lead_brand_configs WHERE client_id = %s AND project = %s",
                        (client_id, "default"),
                    )
                    brand = cur.fetchone()

                if not brand:
                    cur.execute(
                        "SELECT * FROM lead_brand_configs WHERE client_id = %s ORDER BY project LIMIT 1",
                        (client_id,),
                    )
                    brand = cur.fetchone()

                if not brand:
                    # Fallback to client name if no config exists
                    cur.execute("SELECT name FROM lead_clients WHERE id = %s", (client_id,))
                    client = cur.fetchone()
                    if client:
                        return {"agent_name": client['name']}
                return brand
        except Exception as e:
            logger.error(f"Error fetching branding for {client_id}: {e}")
            return None

db_manager = DatabaseManager()
