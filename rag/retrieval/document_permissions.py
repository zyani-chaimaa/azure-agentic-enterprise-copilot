"""Fail-closed document access policy for NEXORA."""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DocumentPrincipal:
    tenant_id: str
    user_id: str
    group_ids: tuple[str, ...] = ()


def _valid_identifier(value: str) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_principal(principal: DocumentPrincipal) -> None:
    if not isinstance(principal, DocumentPrincipal):
        raise ValueError("A valid document principal is required.")

    if not _valid_identifier(principal.tenant_id):
        raise ValueError("Tenant identity is required.")

    if not _valid_identifier(principal.user_id):
        raise ValueError("User identity is required.")

    if not all(_valid_identifier(group) for group in principal.group_ids):
        raise ValueError("Invalid group identity.")


def _normalized_ids(values: Iterable[str] | None) -> set[str]:
    if values is None:
        return set()

    if isinstance(values, str):
        return set()

    return {
        value
        for value in values
        if _valid_identifier(value)
    }


def can_access_document(
    principal: DocumentPrincipal,
    document: dict,
) -> bool:
    """Allow only explicit grants within the same tenant."""

    validate_principal(principal)

    if not isinstance(document, dict):
        return False

    if document.get("tenant_id") != principal.tenant_id:
        return False

    allowed_users = _normalized_ids(
        document.get("allowed_user_ids")
    )

    allowed_groups = _normalized_ids(
        document.get("allowed_group_ids")
    )

    if principal.user_id in allowed_users:
        return True

    return bool(
        set(principal.group_ids).intersection(allowed_groups)
    )


def build_document_security_filter(
    principal: DocumentPrincipal,
) -> str:
    """Build an Azure AI Search OData authorization filter."""

    validate_principal(principal)

    def escape(value: str) -> str:
        return value.replace("'", "''")

    tenant = escape(principal.tenant_id)
    user = escape(principal.user_id)

    clauses = [
        f"allowed_user_ids/any(u: u eq '{user}')"
    ]

    groups = sorted(set(principal.group_ids))

    for group in groups:
        if not _valid_identifier(group):
            raise ValueError("Invalid group identity.")

        group_value = escape(group)

        clauses.append(
            "allowed_group_ids/any("
            f"g: g eq '{group_value}'"
            ")"
        )

    permissions = " or ".join(clauses)

    return (
        f"tenant_id eq '{tenant}' "
        f"and ({permissions})"
    )
