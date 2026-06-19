"""
tests/helpers.py — Test doubles (JWT tokens, fake LLM).
"""
import datetime

import jwt
from types import SimpleNamespace

TEST_JWT_SECRET = "test-secret-key"


def make_access_token(user_id="user-123", secret=TEST_JWT_SECRET, algorithm="HS256",
                      token_type="access", expired=False, user_id_claim="user_id"):
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now - datetime.timedelta(minutes=5) if expired else now + datetime.timedelta(minutes=30)
    claims = {user_id_claim: user_id, "token_type": token_type, "iat": now, "exp": exp, "jti": "t"}
    return jwt.encode(claims, secret, algorithm=algorithm)


def auth_header(token=None):
    return {"Authorization": f"Bearer {token or make_access_token()}"}


def text_completion(content):
    """Mimic the OpenAI SDK response shape for a non-streaming completion."""
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeLLM:
    """Stand-in OpenAI client returning queued completions."""

    def __init__(self, completions):
        self._completions = list(completions)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, *args, **kwargs):
        self.calls.append(kwargs)
        if not self._completions:
            raise AssertionError("FakeLLM ran out of completions")
        return self._completions.pop(0)
