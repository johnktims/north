import logging
import os

import psycopg2

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'DEBUG').upper()
logger = logging.getLogger()
logger.setLevel(log_level)

def get_db_connection():
    """
    Create and return a database connection.

    This function creates a new connection to the PostgreSQL database
    using environment variables for configuration.

    Returns:
        psycopg2.connection: A connection to the PostgreSQL database
    """
    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        database=os.environ.get("PGDATABASE", "users"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", "example"),
        port=os.environ.get("PGPORT", "5432"),
    )
    logger.debug("Database connection established successfully")
    return conn
