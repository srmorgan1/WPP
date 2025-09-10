import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from wpp.database.db import get_db_connection
from wpp.ref_matcher import (
    PBT_REGEX,
    IrregularTenantRefStrategy,
    MatchingStrategy,
    MatchResult,
    MatchValidationException,
    NoHyphenRegexStrategy,
    PBRegexStrategy,
    PBTRegex3Strategy,
    PBTRegex4Strategy,
    PRegexStrategy,
    PropertyBlockTenantRefMatcher,
    PTRegexStrategy,
    RegexDoubleCheckStrategy,
    RegexStrategy,
    SpecialCaseStrategy,
    checkForIrregularTenantRefInDatabase,
    checkTenantExists,
    correctKnownCommonErrors,
    doubleCheckTenantRef,
    getPropertyBlockAndTenantRefsFromRegexMatch,
    matchTransactionRef,
    postProcessPropertyBlockTenantRefs,
    recodeSpecialBlockReferenceCases,
    recodeSpecialPropertyReferenceCases,
    removeDCReferencePostfix,
)


class MockStrategy(MatchingStrategy):
    """Mock strategy for testing."""

    def __init__(self, return_value=None):
        if return_value is None:
            self.return_result = MatchResult.no_match()
        elif return_value == (None, None, None):
            self.return_result = MatchResult.no_match()
        else:
            property_ref, block_ref, tenant_ref = return_value
            self.return_result = MatchResult.match(property_ref, block_ref, tenant_ref)

    def match(self, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        return self.return_result


def test_matching_strategy_name_method():
    """Test that MatchingStrategy.name() returns class name."""
    strategy = MockStrategy()
    assert strategy.name() == "MockStrategy"

    # Test with actual strategies
    regex_strategy = RegexStrategy(PBT_REGEX)
    assert regex_strategy.name() == "RegexStrategy"

    irregular_strategy = IrregularTenantRefStrategy()
    assert irregular_strategy.name() == "IrregularTenantRefStrategy"


def test_checkTenantExists_with_none_result():
    """Test checkTenantExists when tenant doesn't exist."""
    # Create in-memory database
    conn = get_db_connection(":memory:")
    cursor = conn.cursor()

    # Create Tenants table without any data
    cursor.execute("CREATE TABLE Tenants (tenant_ref TEXT, tenant_name TEXT)")

    # Test with non-existent tenant
    result = checkTenantExists(cursor, "999-99-999")
    assert result is False

    conn.close()


def test_matchTransactionRef_edge_cases():
    """Test matchTransactionRef with edge cases."""
    # Test with empty tenant name (should return False)
    result = matchTransactionRef("", "some transaction ref")
    assert result is False

    # Test with very short common substring (less than 4 chars)
    result = matchTransactionRef("abc", "xyz")
    assert result is False

    # Test with exactly 4 char common substring (should return True)
    result = matchTransactionRef("abcdef", "abcd123")
    assert result is True


def test_removeDCReferencePostfix():
    """Test removeDCReferencePostfix function."""
    # Test with None input
    assert removeDCReferencePostfix(None) is None

    # Test with DC postfix
    assert removeDCReferencePostfix("123-45-678 DC") == "123-45-678"
    assert removeDCReferencePostfix("123-45-678DC") == "123-45-678"

    # Test without DC postfix
    assert removeDCReferencePostfix("123-45-678") == "123-45-678"


def test_correctKnownCommonErrors():
    """Test correctKnownCommonErrors function."""
    # Test specific error correction for property 094
    _, _, tenant_ref = correctKnownCommonErrors("094", "094-01", "094-01-O23")
    assert tenant_ref == "094-01-023"

    # Test with None tenant_ref
    _, _, tenant_ref = correctKnownCommonErrors("094", "094-01", None)
    assert tenant_ref is None

    # Test with different property (no correction)
    _, _, tenant_ref = correctKnownCommonErrors("095", "095-01", "095-01-O23")
    assert tenant_ref == "095-01-O23"


def test_recodeSpecialPropertyReferenceCases():
    """Test recodeSpecialPropertyReferenceCases function."""
    # Test 020-03 recoding
    prop_ref, _, _ = recodeSpecialPropertyReferenceCases("020", "020-03", "020-03-001")
    assert prop_ref == "020A"

    # Test 064-01 recoding
    prop_ref, _, _ = recodeSpecialPropertyReferenceCases("064", "064-01", "064-01-001")
    assert prop_ref == "064A"

    # Test no recoding needed
    prop_ref, _, _ = recodeSpecialPropertyReferenceCases("021", "021-01", "021-01-001")
    assert prop_ref == "021"


def test_recodeSpecialBlockReferenceCases():
    """Test recodeSpecialBlockReferenceCases function."""
    # Test 101-02 recoding
    _, block_ref, tenant_ref = recodeSpecialBlockReferenceCases("101", "101-02", "101-02-001")
    assert block_ref == "101-01"
    assert tenant_ref == "101-01-001"

    # Test with None tenant_ref
    _, block_ref, tenant_ref = recodeSpecialBlockReferenceCases("101", "101-02", None)
    assert block_ref == "101-01"
    assert tenant_ref is None

    # Test no recoding needed
    _, block_ref, tenant_ref = recodeSpecialBlockReferenceCases("102", "102-01", "102-01-001")
    assert block_ref == "102-01"


def test_getPropertyBlockAndTenantRefsFromRegexMatch():
    """Test getPropertyBlockAndTenantRefsFromRegexMatch function."""
    # Test with valid match
    pattern = re.compile(r"(\d{3})-(\d{2})-(\d{3})")
    match = pattern.search("123-45-678")
    prop_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
    assert prop_ref == "123"
    assert block_ref == "123-45"
    assert tenant_ref == "123-45-678"

    # Test with None match
    prop_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(None)
    assert prop_ref is None
    assert block_ref is None
    assert tenant_ref is None


def test_postProcessPropertyBlockTenantRefs():
    """Test postProcessPropertyBlockTenantRefs function."""
    # Test filtering out refs with Z or Y
    result = postProcessPropertyBlockTenantRefs("123", "123-01", "123-01-Z01")
    assert result == (None, None, None)

    result = postProcessPropertyBlockTenantRefs("123", "123-01", "123-01-Y01")
    assert result == (None, None, None)

    # Test filtering out property refs >= 900
    result = postProcessPropertyBlockTenantRefs("900", "900-01", "900-01-001")
    assert result == (None, None, None)

    result = postProcessPropertyBlockTenantRefs("999", "999-01", "999-01-001")
    assert result == (None, None, None)

    # Test valid refs that should pass through
    result = postProcessPropertyBlockTenantRefs("123", "123-01", "123-01-001")
    assert result == ("123", "123-01", "123-01-001")


def test_special_case_strategy_edge_cases():
    """Test SpecialCaseStrategy with edge cases."""
    strategy = SpecialCaseStrategy()

    # Test without database cursor using actual special case properties from config (138, 157)
    # Pattern expects (\d{3})-(\d{2})-(\d{4}[A-Z]?) format
    result = strategy.match("138-01-0111", None)  # 138 is in special case properties
    assert result.property_ref == "138"
    assert result.block_ref == "138-01"
    assert result.tenant_ref == "138-01-0111"
    assert result.matched is True

    # Test with property not in special cases - should raise exception
    with pytest.raises(MatchValidationException):
        strategy.match("999-01-0123", None)


def test_pbt_regex4_strategy_validation():
    """Test PBTRegex4Strategy validation logic."""
    strategy = PBTRegex4Strategy()

    # Create in-memory database for testing
    conn = get_db_connection(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE Tenants (tenant_ref TEXT, tenant_name TEXT)")

    # Test validation failure
    with pytest.raises(MatchValidationException):
        strategy.match("12-34-567", cursor)  # Should fail validation

    conn.close()


def test_property_block_tenant_ref_matcher_logging():
    """Test PropertyBlockTenantRefMatcher CSV logging."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create matcher with custom log file
        matcher = PropertyBlockTenantRefMatcher()
        matcher.log_file = Path(temp_dir) / "test_ref_matcher.csv"
        matcher._setup_log_file()

        # Add a simple strategy
        matcher.add_strategy(MockStrategy(return_value=("123", "123-01", "123-01-001")))

        # Test matching
        result = matcher.match("123-01-001", None)
        assert result == ("123", "123-01", "123-01-001")

        # Verify log file was created and contains data
        assert matcher.log_file.exists()
        content = matcher.log_file.read_text()
        assert "description,property_ref,block_ref,tenant_ref,strategy" in content
        assert "123-01-001,123,123-01,123-01-001,MockStrategy" in content


def test_property_block_tenant_ref_matcher_no_match():
    """Test PropertyBlockTenantRefMatcher when no strategy matches."""
    with tempfile.TemporaryDirectory() as temp_dir:
        matcher = PropertyBlockTenantRefMatcher()
        matcher.log_file = Path(temp_dir) / "test_no_match.csv"
        matcher._setup_log_file()

        # Add strategy that returns None
        matcher.add_strategy(MockStrategy(return_value=(None, None, None)))

        # Test no match
        result = matcher.match("nomatch", None)
        assert result == (None, None, None)

        # Verify logging of no match
        content = matcher.log_file.read_text()
        assert "nomatch,,,,NoMatch" in content


def test_property_block_tenant_ref_matcher_validation_exception():
    """Test PropertyBlockTenantRefMatcher handling of MatchValidationException."""

    class FailingStrategy(MatchingStrategy):
        def match(self, description: str, db_cursor: sqlite3.Cursor | None):
            # First return a match, then raise validation exception
            raise MatchValidationException("Validation failed")

    with tempfile.TemporaryDirectory() as temp_dir:
        matcher = PropertyBlockTenantRefMatcher()
        matcher.log_file = Path(temp_dir) / "test_validation_fail.csv"
        matcher._setup_log_file()

        # Add failing strategy
        matcher.add_strategy(FailingStrategy())

        # Test validation failure
        result = matcher.match("test", None)
        assert result == (None, None, None)

        # Verify logging of validation failure
        content = matcher.log_file.read_text()
        assert "test,,,,FailingStrategy" in content


def test_no_hyphen_regex_strategy():
    """Test NoHyphenRegexStrategy with various patterns."""
    strategy = NoHyphenRegexStrategy()

    # Test successful match
    result = strategy.match("123 45 678", None)
    assert result.property_ref == "123"
    assert result.block_ref == "123-45"
    assert result.tenant_ref == "123-45-678"
    assert result.matched is True

    # Test no match
    result = strategy.match("no numbers here", None)
    assert result.matched is False


def test_checkForIrregularTenantRefInDatabase():
    """Test checkForIrregularTenantRefInDatabase function."""
    # Create in-memory database
    conn = get_db_connection(":memory:")
    cursor = conn.cursor()

    # Create table and add test data
    cursor.execute("CREATE TABLE IrregularTransactionRefs (tenant_ref TEXT, transaction_ref_pattern TEXT)")
    cursor.execute("INSERT INTO IrregularTransactionRefs VALUES ('123-45-678', 'SPECIAL_REF')")

    # Test finding irregular ref
    result = checkForIrregularTenantRefInDatabase("SPECIAL_REF", cursor)
    # This will depend on the getPropertyBlockAndTenantRefs implementation
    # For now, just test that it doesn't crash and returns MatchResult
    assert isinstance(result, MatchResult)
    assert result.matched is True
    assert result.property_ref == "123"
    assert result.block_ref == "123-45"
    assert result.tenant_ref == "123-45-678"

    # Test with None cursor
    result = checkForIrregularTenantRefInDatabase("anything", None)
    assert isinstance(result, MatchResult)
    assert result.matched is False

    conn.close()


def test_pt_regex_strategy():
    """Test PTRegexStrategy."""
    strategy = PTRegexStrategy()

    # Test matching pattern like "123-456"
    result = strategy.match("123-456", None)
    assert result.property_ref == "123"
    assert result.block_ref == "01"  # Note: block_ref defaults to "01"
    assert result.tenant_ref == "456"
    assert result.matched is True

    # Test no match
    result = strategy.match("nomatch", None)
    assert result.matched is False


def test_pb_regex_strategy():
    """Test PBRegexStrategy."""
    strategy = PBRegexStrategy()

    # Test matching pattern like "123-45"
    result = strategy.match("123-45", None)
    assert result.property_ref == "123"
    assert result.block_ref == "123-45"
    assert result.tenant_ref is None  # tenant_ref is None for PB pattern
    assert result.matched is True

    # Test no match
    result = strategy.match("nomatch", None)
    assert result.matched is False


def test_p_regex_strategy():
    """Test PRegexStrategy."""
    strategy = PRegexStrategy()

    # Test matching pattern like "123"
    result = strategy.match(" 123 ", None)  # Needs spaces around for P_REGEX
    assert result.property_ref == "123"
    assert result.block_ref is None
    assert result.tenant_ref is None  # Only property_ref is set
    assert result.matched is True

    # Test no match
    result = strategy.match("nomatch", None)
    assert result.matched is False


def test_double_check_tenant_ref():
    """Test doubleCheckTenantRef function."""

    # Create mock cursor
    class MockCursor:
        def __init__(self, tenant_exists=True, tenant_name="Test Tenant"):
            self.tenant_exists = tenant_exists
            self.tenant_name = tenant_name

        def execute(self, sql, params):
            pass

        def fetchone(self):
            if self.tenant_exists:
                return (self.tenant_name,)
            return None

    # Test successful validation
    cursor = MockCursor(tenant_exists=True, tenant_name="JOHN SMITH")
    result = doubleCheckTenantRef(cursor, "123-01-001", "JOHN SMITH reference")
    assert result is True

    # Test tenant doesn't exist
    cursor = MockCursor(tenant_exists=False)
    result = doubleCheckTenantRef(cursor, "999-99-999", "any reference")
    assert result is False


def test_regex_double_check_strategy():
    """Test RegexDoubleCheckStrategy validation."""

    class TestRegexDoubleCheckStrategy(RegexDoubleCheckStrategy):
        def __init__(self):
            super().__init__(PBT_REGEX)

    strategy = TestRegexDoubleCheckStrategy()

    # Test without database cursor (should work)
    result = strategy.match("123-01-001", None)
    assert result.property_ref == "123"

    # Test with mock cursor that returns invalid tenant
    class MockCursor:
        def execute(self, sql, params):
            pass

        def fetchone(self):
            return None  # Tenant doesn't exist

    # Should raise exception for non-existent tenant
    with pytest.raises(MatchValidationException):
        strategy.match("123-01-001", MockCursor())


def test_pbt_regex3_strategy_fallback():
    """Test PBTRegex3Strategy fallback logic."""
    strategy = PBTRegex3Strategy()

    # Create a mock cursor that always returns None (tenant doesn't exist)
    class MockCursor:
        def execute(self, sql, params):
            pass

        def fetchone(self):
            return None

    # Test the fallback logic with 2-digit tenant (line 211-214)
    # This should trigger the fallback to add "0" prefix to tenant
    with pytest.raises(MatchValidationException):
        # Pattern that matches PBT_REGEX3: property-block-XX format
        strategy.match("123-01-55", MockCursor())


def test_special_case_strategy_without_database():
    """Test SpecialCaseStrategy without database cursor."""
    strategy = SpecialCaseStrategy()

    # Test valid property in special cases list (157 is in SPECIAL_CASE_PROPERTIES)
    result = strategy.match("157-01-0114A", None)
    assert result.property_ref == "157"
    assert result.block_ref == "157-01"
    assert result.tenant_ref == "157-01-0114A"
    assert result.matched is True

    # Test another valid special case property
    result = strategy.match("138-01-0123", None)
    assert result.property_ref == "138"
    assert result.block_ref == "138-01"
    assert result.tenant_ref == "138-01-0123"
    assert result.matched is True

    # Test property not in special cases should fail validation
    with pytest.raises(MatchValidationException, match="property not in special cases list"):
        strategy.match("999-01-0123", None)


def test_abstract_matching_strategy():
    """Test abstract MatchingStrategy methods."""
    # Test that we can't instantiate abstract class
    with pytest.raises(TypeError):
        MatchingStrategy()

    # Test name method on concrete strategy
    strategy = PBRegexStrategy()
    assert strategy.name() == "PBRegexStrategy"


def test_match_validation_exception():
    """Test MatchValidationException."""
    exception = MatchValidationException("Test message")
    assert str(exception) == "Test message"


def test_irregular_tenant_ref_strategy_coverage():
    """Test IrregularTenantRefStrategy for coverage."""
    strategy = IrregularTenantRefStrategy()

    # Test with None cursor (should return no match)
    result = strategy.match("any reference", None)
    assert not result.matched

    # Test name method
    assert strategy.name() == "IrregularTenantRefStrategy"
