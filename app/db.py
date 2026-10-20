import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row

load_dotenv()

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def connect(dbname=None, **kwargs):
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=dbname or os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        **kwargs,
    )


def connect_checkpointer_db(dbname=None):
    return connect(dbname, autocommit=True, row_factory=dict_row)


def setup_database(dbname=None):
    with connect(dbname) as conn:
        conn.execute(SCHEMA_PATH.read_text())

    with connect_checkpointer_db(dbname) as conn:
        PostgresSaver(conn).setup()


if __name__ == "__main__":
    setup_database()
    print("Database is ready")