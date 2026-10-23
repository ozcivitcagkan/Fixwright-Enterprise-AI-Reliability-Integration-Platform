from dotenv import load_dotenv

from app.db import connect
from app.embeddings import get_embeddings, to_pgvector

BATCH_SIZE = 100


def backfill_embeddings(conn, embeddings) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, description FROM incidents WHERE embedding IS NULL ORDER BY id"
        )
        rows = cursor.fetchall()

    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        vectors = embeddings.embed_documents([description for _, description in batch])
        with conn.cursor() as cursor:
            for (row_id, _), vector in zip(batch, vectors):
                cursor.execute(
                    "UPDATE incidents SET embedding = %s::vector WHERE id = %s AND embedding IS NULL",
                    (to_pgvector(vector), row_id),
                )
        conn.commit()

    return len(rows)


if __name__ == "__main__":
    load_dotenv()
    with connect() as conn:
        count = backfill_embeddings(conn, get_embeddings())
    print(f"Backfilled embeddings for {count} incidents")