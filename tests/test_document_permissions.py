"""Regression tests for document-level authorization."""

import pytest

from rag.retrieval.document_permissions import (
    DocumentPrincipal,
    build_document_security_filter,
    can_access_document,
)


@pytest.fixture
def principal():
    return DocumentPrincipal(
        tenant_id="tenant-a",
        user_id="user-1",
        group_ids=("finance",),
    )


def test_explicit_user_permission(principal):
    document = {
        "tenant_id": "tenant-a",
        "allowed_user_ids": ["user-1"],
        "allowed_group_ids": [],
    }

    assert can_access_document(principal, document)


def test_explicit_group_permission(principal):
    document = {
        "tenant_id": "tenant-a",
        "allowed_user_ids": [],
        "allowed_group_ids": ["finance"],
    }

    assert can_access_document(principal, document)


def test_other_user_is_denied(principal):
    document = {
        "tenant_id": "tenant-a",
        "allowed_user_ids": ["user-2"],
        "allowed_group_ids": [],
    }

    assert not can_access_document(principal, document)


def test_other_tenant_is_denied(principal):
    document = {
        "tenant_id": "tenant-b",
        "allowed_user_ids": ["user-1"],
        "allowed_group_ids": ["finance"],
    }

    assert not can_access_document(principal, document)


def test_missing_permissions_are_denied(principal):
    assert not can_access_document(
        principal,
        {"tenant_id": "tenant-a"},
    )


def test_missing_tenant_is_denied(principal):
    assert not can_access_document(
        principal,
        {"allowed_user_ids": ["user-1"]},
    )


def test_empty_permissions_are_denied(principal):
    document = {
        "tenant_id": "tenant-a",
        "allowed_user_ids": [],
        "allowed_group_ids": [],
    }

    assert not can_access_document(principal, document)


def test_missing_principal_is_rejected():
    with pytest.raises(ValueError):
        build_document_security_filter(None)


def test_missing_user_identity_is_rejected():
    principal = DocumentPrincipal(
        tenant_id="tenant-a",
        user_id="",
    )

    with pytest.raises(ValueError):
        build_document_security_filter(principal)


def test_filter_contains_tenant_and_user(principal):
    result = build_document_security_filter(principal)

    assert "tenant_id eq 'tenant-a'" in result
    assert "allowed_user_ids/any" in result
    assert "'user-1'" in result


def test_filter_contains_group(principal):
    result = build_document_security_filter(principal)

    assert "allowed_group_ids/any" in result
    assert "'finance'" in result


def test_filter_escapes_odata_quotes():
    principal = DocumentPrincipal(
        tenant_id="tenant'a",
        user_id="user'1",
        group_ids=("group'1",),
    )

    result = build_document_security_filter(principal)

    assert "tenant''a" in result
    assert "user''1" in result
    assert "group''1" in result


def test_no_implicit_public_access(principal):
    document = {
        "tenant_id": "tenant-a",
        "is_public": True,
    }

    assert not can_access_document(principal, document)
