from app.backfill_embeddings import backfill_embeddings


def test_backfill_fills_only_missing_embeddings(client, db, fake_embeddings):
    db.execute(
        "INSERT INTO incidents (incident_id, description) VALUES ('INC-OLD', 'Database timeout')"
    )
    client.post("/incidents", json={"incident_id": "INC-NEW", "description": "Printer jam"})

    assert backfill_embeddings(db, fake_embeddings) == 1

    missing = db.execute("SELECT count(*) FROM incidents WHERE embedding IS NULL").fetchone()[0]
    assert missing == 0
    assert backfill_embeddings(db, fake_embeddings) == 0