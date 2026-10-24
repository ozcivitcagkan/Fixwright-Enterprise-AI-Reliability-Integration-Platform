MODEL_ID = "claude-haiku-5-5"
MODEL_EFFORT = "medium"
MODEL_MAX_TOKENS = 8000

EMBEDDING_MODEL_ID = "voyage-4"
# Must match vector(1024) in db/schema.sql
EMBEDDING_DIMENSIONS = 1024
# Chosen with evals/retrieval_eval.py: recall 0.94, precision 0.71 on the eval set.
# Missing a relevant incident costs more than showing an extra one, because the
# model can ignore a weak match but cannot use one it never sees.
SIMILARITY_THRESHOLD = 0.45