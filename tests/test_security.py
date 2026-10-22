"""Security regression tests for Microsoft Entra authentication."""

from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException

from app import auth


def make_credentials():
    return SimpleNamespace(credentials="mock-access-token")


def valid_claims():
    return {
        "tid": auth.TENANT_ID,
        "oid": "test-user-object-id",
        "roles": ["Copilot.User"],
        "scp": "Copilot.Access",
    }


def validate_with_mocked_jwt(claims=None, error=None):
    signing_client = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(
            key="mock-public-key"
        )
    )

    with (
        patch.object(auth, "get_jwks_client", return_value=signing_client),
        patch.object(auth.jwt, "decode") as decode,
    ):
        if error is not None:
            decode.side_effect = error
        else:
            decode.return_value = claims

        return auth.validate_access_token(make_credentials())


def test_valid_access_token():
    claims = valid_claims()

    result = validate_with_mocked_jwt(claims)

    assert result == claims


@pytest.mark.parametrize(
    "error",
    [
        jwt.ExpiredSignatureError("Expired token"),
        jwt.InvalidSignatureError("Invalid signature"),
        jwt.InvalidAudienceError("Wrong audience"),
        jwt.InvalidIssuerError("Wrong issuer"),
    ],
)
def test_invalid_tokens_are_rejected(error):
    with pytest.raises(HTTPException) as exc:
        validate_with_mocked_jwt(error=error)

    assert exc.value.status_code == 401


def test_wrong_tenant_is_rejected():
    claims = valid_claims()
    claims["tid"] = "unexpected-tenant"

    with pytest.raises(HTTPException) as exc:
        validate_with_mocked_jwt(claims)

    assert exc.value.status_code == 401


def test_missing_user_identity_is_rejected():
    claims = valid_claims()
    claims.pop("oid")

    with pytest.raises(HTTPException) as exc:
        validate_with_mocked_jwt(claims)

    assert exc.value.status_code == 401


def test_jwks_service_failure_returns_503():
    with patch.object(
        auth,
        "get_jwks_client",
        side_effect=ConnectionError("JWKS unavailable"),
    ):
        with pytest.raises(HTTPException) as exc:
            auth.validate_access_token(make_credentials())

    assert exc.value.status_code == 503


def test_required_role_is_accepted():
    dependency = auth.require_role("Copilot.User")

    assert dependency(valid_claims()) == valid_claims()


def test_missing_role_is_rejected():
    dependency = auth.require_role("Copilot.Admin")

    with pytest.raises(HTTPException) as exc:
        dependency(valid_claims())

    assert exc.value.status_code == 403


def test_human_role_and_scope_are_accepted():
    dependency = auth.require_human_role("Copilot.User")

    assert dependency(valid_claims()) == valid_claims()


def test_human_role_without_scope_is_rejected():
    claims = valid_claims()
    claims["scp"] = ""

    dependency = auth.require_human_role("Copilot.User")

    with pytest.raises(HTTPException) as exc:
        dependency(claims)

    assert exc.value.status_code == 403


def test_human_scope_without_role_is_rejected():
    claims = valid_claims()
    claims["roles"] = []

    dependency = auth.require_human_role("Copilot.User")

    with pytest.raises(HTTPException) as exc:
        dependency(claims)

    assert exc.value.status_code == 403
