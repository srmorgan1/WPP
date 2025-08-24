"""Tests for reference parsing functionality."""

from wpp.UpdateDatabase import getPropertyBlockAndTenantRefs


def _validate_reference_parsing(reference: str, file_type: str) -> tuple[str | None, str | None, str | None, bool, str]:
    """
    Validate reference parsing based on file type.

    Args:
        reference: Reference string to parse
        file_type: Type of file being processed

    Returns:
        Tuple of (property_ref, block_ref, tenant_ref, parsing_failed, error_msg)
    """
    property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefs(reference)
    parsing_failed = False
    error_msg = ""

    if file_type == "General Tenants":
        # For general tenants file, we need tenant reference to be parseable
        if not tenant_ref:
            parsing_failed = True
            error_msg = f"Tenant reference '{reference}' could not be parsed into property-block-tenant format"
    elif file_type == "Estate":
        # For estate file, we need property reference to be parseable
        if not property_ref:
            parsing_failed = True
            error_msg = f"Estate reference '{reference}' could not be parsed to extract property reference"
    elif file_type == "General Idents":
        # For general idents file, we need tenant reference to be parseable
        if not tenant_ref:
            parsing_failed = True
            error_msg = f"Tenant reference '{reference}' could not be parsed to extract tenant reference"

    return property_ref, block_ref, tenant_ref, parsing_failed, error_msg


def test_valid_tenant_references():
    """Test that valid tenant references parse correctly."""
    # Standard tenant reference format that works
    result = getPropertyBlockAndTenantRefs("123-01-001")
    assert result == ("123", "123-01", "123-01-001")

    result = getPropertyBlockAndTenantRefs("045-02-015")
    assert result == ("045", "045-02", "045-02-015")


def test_references_that_dont_parse():
    """Test references that don't match the parsing rules."""
    # "999" references apparently don't parse (may be reserved or have special rules)
    result = getPropertyBlockAndTenantRefs("999-99-999")
    assert result == (None, None, None)


def test_invalid_tenant_references():
    """Test that invalid tenant references return None values."""
    # Invalid formats from real data
    result = getPropertyBlockAndTenantRefs("0Z24-01-001")
    assert result == (None, None, None)

    result = getPropertyBlockAndTenantRefs("020-01-001A")
    assert result == (None, None, None)

    # Empty and whitespace
    result = getPropertyBlockAndTenantRefs("")
    assert result == (None, None, None)

    result = getPropertyBlockAndTenantRefs("   ")
    assert result == (None, None, None)


def test_partial_references():
    """Test partial references that parse some parts."""
    # Property only
    result = getPropertyBlockAndTenantRefs("123")
    property_ref, block_ref, tenant_ref = result
    assert property_ref == "123"
    assert block_ref is None
    assert tenant_ref is None

    # Property and block only
    result = getPropertyBlockAndTenantRefs("123-01")
    property_ref, block_ref, tenant_ref = result
    assert property_ref is not None
    assert block_ref is not None
    assert tenant_ref is None


def test_estate_references():
    """Test that estate references parse correctly."""
    # Estate format (property-00)
    result = getPropertyBlockAndTenantRefs("123-00")
    property_ref, block_ref, tenant_ref = result
    # Should get property and block, but no tenant for estate
    assert property_ref is not None
    assert block_ref is not None
    assert tenant_ref is None


def test_edge_cases():
    """Test edge cases for reference parsing."""
    # None input
    result = getPropertyBlockAndTenantRefs(None)
    assert result == (None, None, None)

    # Non-string input
    result = getPropertyBlockAndTenantRefs(123)
    assert result == (None, None, None)

    # Completely invalid format
    result = getPropertyBlockAndTenantRefs("INVALID")
    assert result == (None, None, None)


def test_validation_logic_general_tenants():
    """Test validation logic for General Tenants file type."""
    # Valid tenant should pass
    property_ref, block_ref, tenant_ref, failed, error_msg = _validate_reference_parsing("123-01-001", "General Tenants")
    assert failed is False
    assert error_msg == ""

    # Invalid reference should fail with appropriate message
    property_ref, block_ref, tenant_ref, failed, error_msg = _validate_reference_parsing("INVALID-REF", "General Tenants")
    assert failed is True
    assert "could not be parsed into property-block-tenant format" in error_msg


def test_validation_logic_estate():
    """Test validation logic for Estate file type."""
    # Valid estate should pass (needs property_ref)
    property_ref, block_ref, tenant_ref, failed, error_msg = _validate_reference_parsing("123-00", "Estate")
    assert failed is False or property_ref is not None  # Should have property_ref

    # Invalid estate should fail
    property_ref, block_ref, tenant_ref, failed, error_msg = _validate_reference_parsing("INVALID-ESTATE", "Estate")
    assert failed is True
    assert "could not be parsed to extract property reference" in error_msg


def test_validation_logic_general_idents():
    """Test validation logic for General Idents file type."""
    # Valid tenant should pass (needs tenant_ref)
    property_ref, block_ref, tenant_ref, failed, error_msg = _validate_reference_parsing("123-01-001", "General Idents")
    assert failed is False

    # Block-only reference should fail (no tenant)
    property_ref, block_ref, tenant_ref, failed, error_msg = _validate_reference_parsing("123-01", "General Idents")
    assert failed is True
    assert "could not be parsed to extract tenant reference" in error_msg


def test_validation_logic_unknown_file_type():
    """Test validation logic with unknown file type."""
    # Should not fail for unknown file types (no validation rules)
    property_ref, block_ref, tenant_ref, failed, error_msg = _validate_reference_parsing("123-01-001", "Unknown File Type")
    assert failed is False
    assert error_msg == ""
