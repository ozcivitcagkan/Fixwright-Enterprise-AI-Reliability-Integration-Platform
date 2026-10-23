import httpx
import pytest
from tenacity import wait_none

from app.embeddings import VoyageEmbeddings


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    monkeypatch.setattr(VoyageEmbeddings._embed.retry, "wait", wait_none())


def voyage_response(vectors):
    return httpx.Response(
        200,
        json={"data": [{"embedding": vector, "index": i} for i, vector in enumerate(vectors)]},
    )


def make_embeddings(responses):
    requests = []

    def handler(request):
        requests.append(request)
        return responses[len(requests) - 1]

    return VoyageEmbeddings("test-key", transport=httpx.MockTransport(handler)), requests


def test_rate_limited_request_is_retried():
    embeddings, requests = make_embeddings([httpx.Response(429), voyage_response([[0.1, 0.2]])])

    assert embeddings.embed_query("database is down") == [0.1, 0.2]
    assert len(requests) == 2


def test_gives_up_after_three_attempts():
    embeddings, requests = make_embeddings([httpx.Response(429)] * 3)

    with pytest.raises(httpx.HTTPStatusError):
        embeddings.embed_query("database is down")
    assert len(requests) == 3


def test_invalid_api_key_is_not_retried():
    embeddings, requests = make_embeddings([httpx.Response(401)])

    with pytest.raises(httpx.HTTPStatusError):
        embeddings.embed_query("database is down")
    assert len(requests) == 1