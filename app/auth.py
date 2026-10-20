# Import a function to cache Microsoft Entra signing keys.
from functools import lru_cache

# Import PyJWT for validating signed access tokens.
import jwt

# Import FastAPI security and dependency utilities.
from fastapi import Depends, HTTPException, Security, status

# Import the HTTP bearer-token authentication scheme.
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


# Identify the trusted Microsoft Entra tenant.
TENANT_ID = "a50c7ddf-24ae-403c-b55b-5f14bd5ad88a"

# Identify the API application registered in Entra ID.
CLIENT_ID = "d55c18fc-68a8-4bbb-a700-248cbc9e732c"

# Define the expected Microsoft Entra token issuer.
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"

# Define the API audiences accepted by our backend.
AUDIENCES = [CLIENT_ID, f"api://{CLIENT_ID}"]

# Locate Microsoft's public signing keys for our tenant.
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

# Require an Authorization: Bearer header.
bearer_scheme = HTTPBearer(auto_error=True)


# Cache the signing-key client to avoid recreating it per request.
@lru_cache(maxsize=1)
def get_jwks_client():
    # Create a client that retrieves Microsoft's public signing keys.
    return jwt.PyJWKClient(JWKS_URL)


# Validate a Microsoft Entra ID access token.
def validate_access_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> dict:

    # Extract the access token from the Authorization header.
    token = credentials.credentials

    try:
        # Select the trusted public key matching the token signature.
        signing_key = get_jwks_client().get_signing_key_from_jwt(token)

        # Verify the token's signature and security claims.
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=AUDIENCES,
            issuer=ISSUER,
            options={
                "require": ["exp", "iat", "nbf", "iss", "aud", "tid"],
            },
            leeway=60,
        )

        # Ensure the token belongs to our configured tenant.
        if claims.get("tid") != TENANT_ID:
            raise jwt.InvalidTokenError("Unexpected tenant.")

        # Require an authenticated subject identity.
        if not claims.get("oid"):
            raise jwt.InvalidTokenError("Missing object identity.")

        # Return the verified claims for authorization checks.
        return claims

    # Reject invalid, expired, or incorrectly signed tokens.
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Fail closed if Microsoft's signing keys cannot be retrieved.
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token validation service unavailable.",
        ) from exc


# Build a reusable dependency that requires an application role.
def require_role(required_role: str):

    # Validate the caller and inspect their assigned roles.
    def check_role(claims: dict = Depends(validate_access_token)) -> dict:

        # Retrieve application roles from the verified access token.
        roles = claims.get("roles", [])

        # Deny access when the required role is missing.
        if required_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )

        # Return the authenticated identity and verified claims.
        return claims

    # Return the dependency for use in FastAPI endpoints.
    return check_role


# Create a security dependency for human users.
def require_human_role(required_role: str):

    # Define the function FastAPI will call for each request.
    def check_human_role(
        claims: dict = Depends(validate_access_token),
    ) -> dict:

        # Check that the authenticated user has the required role.
        if required_role not in claims.get("roles", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )

        # Read the delegated permissions from the validated access token.
        scopes = claims.get("scp", "").split()

        # Require our API's specific delegated permission.
        if "Copilot.Access" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Copilot.Access permission is required.",
            )

        # Return the verified identity.
        return claims

    # Return the security dependency to FastAPI.
    return check_human_role