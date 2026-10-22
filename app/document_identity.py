"""Build a document principal from validated Microsoft Entra claims."""

from rag.retrieval.document_permissions import DocumentPrincipal


def principal_from_claims(claims: dict) -> DocumentPrincipal:
    if not isinstance(claims, dict):
        raise PermissionError("Validated claims are required.")

    tenant_id = claims.get("tid")
    user_id = claims.get("oid")

    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise PermissionError("Missing tenant identity.")

    if not isinstance(user_id, str) or not user_id.strip():
        raise PermissionError("Missing user identity.")

    claim_names = claims.get("_claim_names") or {}

    if not isinstance(claim_names, dict):
        raise PermissionError("Invalid token metadata.")

    if claims.get("hasgroups") or "groups" in claim_names:
        raise PermissionError("Group overage requires resolution.")

    groups = claims.get("groups", [])

    if not isinstance(groups, list) or not all(
        isinstance(group, str) and bool(group.strip())
        for group in groups
    ):
        raise PermissionError("Invalid group claims.")

    return DocumentPrincipal(
        tenant_id=tenant_id,
        user_id=user_id,
        group_ids=tuple(groups),
    )
