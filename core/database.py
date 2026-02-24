import streamlit as st
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import os
from contextlib import contextmanager
import traceback

# Inicializar el pool de conexiones (solo una vez, usando cache_resource)
@st.cache_resource
def init_connection_pool():
    """Inicializa y devuelve un pool de conexiones a PostgreSQL."""
    try:
        # Obtener configuración de secrets.toml o variables de entorno
        POSTGRES_CONFIG = {
            "host": st.secrets.get("postgres", {}).get("host", os.getenv("DB_HOST", "localhost")),
            "port": st.secrets.get("postgres", {}).get("port", os.getenv("DB_PORT", "5432")),
            "database": st.secrets.get("postgres", {}).get("database", os.getenv("DB_NAME", "hotel_db")),
            "user": st.secrets.get("postgres", {}).get("user", os.getenv("DB_USER", "postgres")),
            "password": st.secrets.get("postgres", {}).get("password", os.getenv("DB_PASSWORD", ""))
        }
        
        connection_pool = pool.SimpleConnectionPool(
            1, 10,
            **POSTGRES_CONFIG,
            cursor_factory=RealDictCursor
        )
        return connection_pool
    except Exception as e:
        st.error(f"❌ Error al conectar a la base de datos: {e}")
        return None

def get_connection():
    """Obtiene una conexión del pool."""
    pool = init_connection_pool()
    if pool:
        try:
            return pool.getconn()
        except Exception as e:
            st.error(f"❌ Error al obtener conexión del pool: {e}")
            return None
    return None

def return_connection(conn):
    """Devuelve la conexión al pool."""
    pool = init_connection_pool()
    if pool and conn:
        pool.putconn(conn)

def run_query(query, params=None):
    """
    Ejecuta una consulta SQL y devuelve los resultados.
    SOLO PARA CONSULTAS DE LECTURA (SELECT)
    """
    conn = None
    try:
        conn = get_connection()
        if not conn:
            return None
        
        with conn.cursor() as cur:
            cur.execute(query, params)
            
            if cur.description:  # Es una SELECT
                result = cur.fetchall()
                return result
            else:
                conn.commit()
                return [{"rowcount": cur.rowcount}]
    except Exception as e:
        st.error(f"Error ejecutando query: {e}")
        return None
    finally:
        if conn:
            return_connection(conn)

def execute_transaction(queries):
    """
    Ejecuta múltiples queries en UNA SOLA TRANSACCIÓN.
    queries: lista de tuplas (query, params)
    """
    conn = None
    results = []
    
    try:
        conn = get_connection()
        if not conn:
            st.error("❌ No se pudo obtener conexión")
            return False, []
        
        with conn.cursor() as cur:
            last_inserted_id = None
            
            for i, (query, params) in enumerate(queries):
                
                # Si tenemos un ID de inserción anterior, reemplazar TODOS los Nones
                if last_inserted_id is not None:
                    # Convertir a lista para modificar
                    if isinstance(params, tuple):
                        params = list(params)
                    
                    # Reemplazar TODOS los Nones con el último ID insertado
                    for j, param in enumerate(params):
                        if param is None:
                            params[j] = last_inserted_id
                    
                # Ejecutar
                cur.execute(query, params)
                
                # Obtener resultado
                if cur.description:
                    result = cur.fetchall()
                    results.append(result)
                    
                    # Guardar el ID si es una consulta con RETURNING id
                    if result and len(result) > 0 and 'id' in result[0]:
                        last_inserted_id = result[0]['id']
                else:
                    # Para INSERT sin RETURNING
                    results.append([{"rowcount": cur.rowcount}])
            
            conn.commit()
            return True, results
            
    except Exception as e:
        if conn:
            conn.rollback()
        st.error(f"❌ Error en transacción: {e}")
        import traceback
        st.error(traceback.format_exc())
        return False, []
        
    finally:
        if conn:
            return_connection(conn)