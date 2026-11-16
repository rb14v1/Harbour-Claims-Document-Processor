"""
Thin wrapper around Azure OpenAI chat completions and embeddings, via the
`openai` package's `AzureOpenAI` client.

Real calls are used when AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY are
both set. Otherwise both chat_completion() and generate_embedding() fall back
to deterministic, SHA256-seeded stub output so demos/tests never require
network access or incur cost.
"""

import hashlib

from decouple import config

AZURE_OPENAI_ENDPOINT = config("AZURE_OPENAI_ENDPOINT", default="")
AZURE_OPENAI_API_KEY = config("AZURE_OPENAI_API_KEY", default="")
OPENAI_CHAT_MODEL = config("OPENAI_CHAT_MODEL", default="gpt-5.6-sol")
OPENAI_EMBEDDING_MODEL = config("OPENAI_EMBEDDING_MODEL", default="text-embedding-3-large")
EMBEDDING_DIMENSIONS = config("EMBEDDING_DIMENSIONS", default=1536, cast=int)

AZURE_OPENAI_API_VERSION = "2024-06-01"


def _is_real():
    return bool(AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY)


def _client():  # pragma: no cover - requires real Azure creds
    from openai import AzureOpenAI

    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def pad_vector(vector, dims=None):
    """Truncates or zero-pads `vector` to exactly `dims` entries."""
    dims = dims or EMBEDDING_DIMENSIONS
    vector = list(vector)
    if len(vector) >= dims:
        return vector[:dims]
    return vector + [0.0] * (dims - len(vector))


def chat_completion(messages, model=None):
    """
    `messages` is a list of {"role": ..., "content": ...} dicts, same shape
    as the OpenAI chat completions API. Returns the assistant's text content.
    """
    if _is_real():  # pragma: no cover - requires real Azure creds
        client = _client()
        response = client.chat.completions.create(
            model=model or OPENAI_CHAT_MODEL,
            messages=messages,
        )
        return response.choices[0].message.content
    return _stub_chat_completion(messages)


def generate_embedding(text, model=None):
    """Returns a list[float] of length EMBEDDING_DIMENSIONS for `text`."""
    if _is_real():  # pragma: no cover - requires real Azure creds
        client = _client()
        response = client.embeddings.create(model=model or OPENAI_EMBEDDING_MODEL, input=text)
        return pad_vector(response.data[0].embedding)
    return _stub_embedding(text)


def _stub_chat_completion(messages):
    joined = " | ".join(f"{m.get('role', 'user')}:{m.get('content', '')}" for m in messages)
    seed = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break
    snippet = " ".join(last_user.split())[:280]
    return f"[stub-ai-summary seed={seed[:12]}] {snippet}"


def _stub_embedding(text):
    if not isinstance(text, (bytes, bytearray)):
        text = str(text).encode("utf-8")
    digest = hashlib.sha256(text).digest()
    vector = []
    for i in range(EMBEDDING_DIMENSIONS):
        byte = digest[i % len(digest)]
        value = ((byte + i * 37) % 256) / 127.5 - 1.0
        vector.append(value)
    return pad_vector(vector)
