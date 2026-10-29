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

SESSION_COOKIE_NAME = "fixwright_session"
# Fixed lifetime: the cookie is only re-sent when the session changes, so it does not slide
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
SESSION_SECRET_MIN_LENGTH = 32

DEMO_DAILY_ANALYSIS_LIMIT = 30