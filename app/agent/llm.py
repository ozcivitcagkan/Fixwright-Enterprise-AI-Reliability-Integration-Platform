from langchain_anthropic import ChatAnthropic

from app.config import MODEL_EFFORT, MODEL_ID, MODEL_MAX_TOKENS


def get_chat_model():
    return ChatAnthropic(
        model=MODEL_ID,
        effort=MODEL_EFFORT,
        max_tokens=MODEL_MAX_TOKENS,
    )