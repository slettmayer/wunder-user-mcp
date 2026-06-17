import base64
import json
import time

from wunder_user_mcp.auth import _decode_jwt_exp


def _make_jwt(payload: dict) -> str:
    def b64(obj: dict) -> str:
        raw = json.dumps(obj).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{b64({'alg': 'HS256', 'typ': 'JWT'})}.{b64(payload)}.signature"


def test_decode_jwt_exp_reads_exp():
    exp = int(time.time()) + 3600
    token = _make_jwt({"sub": "user", "exp": exp})
    assert _decode_jwt_exp(token) == float(exp)


def test_decode_jwt_exp_missing_exp():
    token = _make_jwt({"sub": "user"})
    assert _decode_jwt_exp(token) is None


def test_decode_jwt_exp_malformed():
    assert _decode_jwt_exp("not-a-jwt") is None
    assert _decode_jwt_exp("a.b") is None
