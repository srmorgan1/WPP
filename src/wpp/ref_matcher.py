from __future__ import annotations

import csv
import re
import sqlite3
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wpp.config import (
    get_alphanumeric_properties,
    get_commercial_properties,
    get_config,
    get_digit_letter_suffix_properties,
    get_double_zero_letter_properties,
    get_exclude_z_suffix_properties,
    get_industrial_estate_properties,
    get_letter_digit_letter_properties,
    get_special_case_properties,
    get_three_letter_code_properties,
    get_two_letter_code_properties,
    get_wpp_ref_matcher_log_file,
)
from wpp.constants import (
    DEBIT_CARD_SUFFIX,
    EXCLUDED_TENANT_REF_CHARACTERS,
    MIN_TENANT_REF_LENGTH_FOR_ERROR_CORRECTION,
    MINIMUM_TENANT_NAME_MATCH_LENGTH,
    MINIMUM_VALID_PROPERTY_REF,
    PROPERTY_094_CORRECTION_POSITION,
    PROPERTY_094_ERROR_CHAR,
    SPECIAL_BLOCK_RECODING,
    SPECIAL_PROPERTY_RECODING,
)
from wpp.data_classes import MatchLogData
from wpp.db import checkTenantExists, get_single_value, getTenantName
from wpp.utils import getLongestCommonSubstring


#
# Data Classes
#
@dataclass
class MatchResult:
    """Result of a property/block/tenant reference matching attempt."""

    property_ref: str | None = None
    block_ref: str | None = None
    tenant_ref: str | None = None
    matched: bool = False
    excluded: bool = False

    @classmethod
    def no_match(cls) -> MatchResult:
        """Create a MatchResult representing no match found."""
        return cls(matched=False)

    @classmethod
    def match(cls, property_ref: str | None, block_ref: str | None, tenant_ref: str | None) -> MatchResult:
        """Create a MatchResult representing a successful match."""
        return cls(property_ref=property_ref, block_ref=block_ref, tenant_ref=tenant_ref, matched=True)

    @classmethod
    def excluded_match(cls, property_ref: str | None, block_ref: str | None, tenant_ref: str | None) -> MatchResult:
        """Create a MatchResult representing an excluded match (e.g., Z suffix exclusion)."""
        return cls(property_ref=property_ref, block_ref=block_ref, tenant_ref=tenant_ref, matched=True, excluded=True)

    def is_excluded(self) -> bool:
        """Check if this result represents an excluded match."""
        return self.excluded

    def to_tuple(self) -> tuple[str | None, str | None, str | None]:
        """Convert to the legacy tuple format for backward compatibility."""
        return (self.property_ref, self.block_ref, self.tenant_ref)


#
# SQL
#
SELECT_IRREGULAR_TRANSACTION_TENANT_REF_SQL = "select tenant_ref from IrregularTransactionRefs where instr(?, transaction_ref_pattern) > 0;"

#
# Regular expressions
#
PBT_REGEX = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})-(\d{3})\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX2 = re.compile(r"(?:^|\s+|,)(\d{3})\s-\s(\d{2})\s-\s(\d{3})\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX3 = re.compile(r"(?:^|\s+|,)(\d{3})-0?(\d{2})-(\d{2,3})\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX4 = re.compile(r"(?:^|\s+|,)(\d{2})-0?(\d{2})-(\d{3})\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_NO_TERMINATING_SPACE = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})-(\d{3})(?:$|\s*|,|/)")
PBT_REGEX_NO_BEGINNING_SPACE = re.compile(r"(?:^|\s*|,)(\d{3})-(\d{2})-(\d{3})(?:$|\s+|,|/)")
PBT_REGEX_SPECIAL_CASES = re.compile(
    r"(?:^|\s+|,|\.)(\d{3})-{1,2}0?(\d{2})-{1,2}(\w{2,5})\s?(?:DC)?(?:$|\s+|,|/)",
    re.ASCII,
)
PBT_REGEX_NO_HYPHENS = re.compile(r"(?:^|\s+|,)(\d{3})\s{0,2}0?(\d{2})\s{0,2}(\d{3})(?:$|\s+|,|/)")
PBT_REGEX_NO_HYPHENS_SPECIAL_CASES = re.compile(r"(?:^|\s+|,)(\d{3})\s{0,2}0?(\d{2})\s{0,2}(\w{3})(?:$|\s+|,|/)", re.ASCII)
PBT_REGEX_FWD_SLASHES = re.compile(r"(?:^|\s+|,)(\d{3})/0?(\d{2})/(\d{3})\s?(?:DC)?(?:$|\s+|,|/)")
PT_REGEX = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{3})(?:$|\s+|,|/)")
PB_REGEX = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})(?:$|\s+|,|/)")
P_REGEX = re.compile(r"(?:^|\s+)(\d{3})(?:$|\s+)")

# New regex patterns for 2025-08-04 scenario tenant reference formats
PBT_REGEX_ALPHA_SUFFIX = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})-(\d{3}[A-Z])\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_COM_BLOCK = re.compile(r"(?:^|\s+|,)(\d{3})-(COM)-(\d{3}[A-Z]?)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_COM_TENANT = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})-(COM)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_INDUSTRIAL_ESTATE = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})-([A-Z]\d?)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_DIGIT_LETTER_SUFFIX = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})-(\d{3}[A-Z])\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_LETTER_DIGIT_LETTER = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})-(0[A-Z]\d)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_DOUBLE_ZERO_LETTER = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})-(00[A-Z])\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_THREE_LETTER_CODE = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})-([A-Z]{3})\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_TWO_LETTER_CODE = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})-([A-Z]{2})\s?(?:DC)?(?:$|\s+|,|/)")
# Regex for catching remaining edge cases and corrupted patterns
PBT_REGEX_CATCH_REMAINDER = re.compile(
    r"(?:^|\s+|,|\.)(\d{3})-{1,2}0?(\d{2})-{1,2}(\w{2,5})\s?(?:DC)?(?:$|\s+|,|/)",
    re.ASCII,
)
# Narrow regex for true special cases (corrupted patterns with name prefixes)
PBT_REGEX_SPECIAL_NARROW = re.compile(r"(?:^|\s+|,)(\d{3})-(\d{2})-(\d{4}[A-Z]?)\s?(?:DC)?(?:$|\s+|,|/)")

# Alphanumeric property patterns for properties like 059A
PBT_REGEX_ALPHANUMERIC = re.compile(r"(?:^|\s+|,)(\d{3}[A-Z])-(\d{2})-(\d{3}[A-Z]?)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_ALPHANUMERIC_NO_HYPHENS = re.compile(r"(?:^|\s+|,)(\d{3}[A-Z])\s{0,2}0?(\d{2})\s{0,2}(\d{3}[A-Z]?)(?:$|\s+|,|/)")
PBT_REGEX_ALPHANUMERIC_FWD_SLASHES = re.compile(r"(?:^|\s+|,)(\d{3}[A-Z])/0?(\d{2})/(\d{3}[A-Z]?)\s?(?:DC)?(?:$|\s+|,|/)")
PB_REGEX_ALPHANUMERIC = re.compile(r"(?:^|\s+|,)(\d{3}[A-Z])-(\d{2})(?:$|\s+|,|/)")
P_REGEX_ALPHANUMERIC = re.compile(r"(?:^|\s+)(\d{3}[A-Z])(?:$|\s+)")


def matchTransactionRef(tenant_name: str, transaction_reference: str) -> bool:
    tnm = re.sub(r"(?:^|\s+)mr?s?\s+", "", tenant_name.lower())
    tnm = re.sub(r"\s+and\s+", "", tnm)
    tnm = re.sub(r"(?:^|\s+)\w\s+", " ", tnm)
    tnm = re.sub(r"[_\W]+", " ", tnm).strip()

    trf = re.sub(r"(?:^|\s+)mr?s?\s+", "", transaction_reference.lower())
    trf = re.sub(r"\s+and\s+", "", trf)
    trf = re.sub(r"(?:^|\s+)\w\s+", " ", trf)
    trf = re.sub(r"\d", "", trf)
    trf = re.sub(r"[_\W]+", " ", trf).strip()

    # Early return for empty tenant name
    if not tenant_name:
        return False

    lcss = getLongestCommonSubstring(tnm, trf)
    # Assume that if the transaction reference has a substring matching
    # one in the tenant name of >= minimum length chars, then this is a match.
    return len(lcss) >= MINIMUM_TENANT_NAME_MATCH_LENGTH


def removeDCReferencePostfix(tenant_ref: str | None) -> str | None:
    """Remove 'DC' from parsed tenant references paid by debit card."""
    # Early return for None or non-DC references
    if not tenant_ref or not tenant_ref.endswith(DEBIT_CARD_SUFFIX):
        return tenant_ref

    return tenant_ref[:-2].strip()


def correctKnownCommonErrors(property_ref: str, block_ref: str, tenant_ref: str | None) -> tuple[str, str, str | None]:
    """Correct known errors in the tenant payment references."""
    # Early return if not the specific property/tenant combination we need to fix
    if property_ref != "094" or not tenant_ref or len(tenant_ref) < MIN_TENANT_REF_LENGTH_FOR_ERROR_CORRECTION or tenant_ref[PROPERTY_094_CORRECTION_POSITION] != PROPERTY_094_ERROR_CHAR:
        return property_ref, block_ref, tenant_ref

    # Fix the 'O' to '0' error in property 094
    tenant_ref = tenant_ref[:PROPERTY_094_CORRECTION_POSITION] + "0" + tenant_ref[PROPERTY_094_CORRECTION_POSITION + 1 :]
    return property_ref, block_ref, tenant_ref


def recodeSpecialPropertyReferenceCases(property_ref: str, block_ref: str, tenant_ref: str | None) -> tuple[str, str, str | None]:
    recoding_key = (property_ref, block_ref)
    if recoding_key in SPECIAL_PROPERTY_RECODING:
        property_ref = SPECIAL_PROPERTY_RECODING[recoding_key]
    return property_ref, block_ref, tenant_ref


def recodeSpecialBlockReferenceCases(property_ref: str, block_ref: str, tenant_ref: str | None) -> tuple[str, str, str | None]:
    recoding_key = (property_ref, block_ref)
    if recoding_key in SPECIAL_BLOCK_RECODING:
        new_block_ref = SPECIAL_BLOCK_RECODING[recoding_key]
        tenant_ref = tenant_ref.replace(block_ref, new_block_ref) if tenant_ref is not None else tenant_ref
        block_ref = new_block_ref
    return property_ref, block_ref, tenant_ref


def getPropertyBlockAndTenantRefsFromRegexMatch(
    match: re.Match,
) -> tuple[str | None, str | None, str | None]:
    property_ref, block_ref, tenant_ref = None, None, None
    if match:
        property_ref = match.group(1)
        block_ref = f"{match.group(1)}-{match.group(2)}"
        tenant_ref = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return property_ref, block_ref, tenant_ref


def doubleCheckTenantRef(db_cursor: sqlite3.Cursor, tenant_ref: str, reference: str) -> bool:
    if not checkTenantExists(db_cursor, tenant_ref):
        return False
    tenant_name = getTenantName(db_cursor, tenant_ref)
    return matchTransactionRef(tenant_name, reference)


def postProcessPropertyBlockTenantRefs(property_ref: str | None, block_ref: str | None, tenant_ref: str | None) -> tuple[str | None, str | None, str | None]:
    # Ignore some property and tenant references, and recode special cases
    # e.g. Block 020-03 belongs to a different property than the other 020-xx blocks.
    if (tenant_ref is not None and any(char in tenant_ref for char in EXCLUDED_TENANT_REF_CHARACTERS)) or (
        property_ref is not None and property_ref.isnumeric() and int(property_ref) >= MINIMUM_VALID_PROPERTY_REF
    ):
        return None, None, None

    # Only apply special recoding if we have non-None property_ref and block_ref
    if property_ref is not None and block_ref is not None:
        property_ref, block_ref, tenant_ref = recodeSpecialPropertyReferenceCases(property_ref, block_ref, tenant_ref)
        property_ref, block_ref, tenant_ref = recodeSpecialBlockReferenceCases(property_ref, block_ref, tenant_ref)

    return property_ref, block_ref, tenant_ref


class MatchingStrategy(ABC):
    @abstractmethod
    def match(self, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        pass

    def name(self) -> str:
        return self.__class__.__name__


class MatchValidationException(Exception):
    """Raise when a matching strategy matches but fails validation"""


class IrregularTenantRefStrategy(MatchingStrategy):
    def match(self, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        result = checkForIrregularTenantRefInDatabase(description, db_cursor)
        return result


class RegexStrategy(MatchingStrategy):
    def __init__(self, regex: re.Pattern):
        self.regex = regex

    def match(self, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        match = re.search(self.regex, description)
        if match:
            return self.process_match(match, description, db_cursor)
        else:
            return MatchResult.no_match()

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        # This was originally a check for the tenant reference in the database with PBT_REGEX (commented out in old code)
        # if db_cursor and not checkTenantExists(db_cursor, tenant_ref):
        #    return MatchResult.no_match()
        property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
        # if db_cursor and not checkTenantExists(db_cursor, tenant_ref):
        #    raise MatchValidationException("Failed to validate tenant reference")
        return MatchResult.match(property_ref, block_ref, tenant_ref)


class RegexDoubleCheckStrategy(RegexStrategy):
    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        result = super().process_match(match, description, db_cursor)

        if db_cursor and result.tenant_ref and not doubleCheckTenantRef(db_cursor, result.tenant_ref, description):
            raise MatchValidationException("Failed to validate tenant reference")
        return result


class PBTRegex3Strategy(RegexStrategy):
    # Match tenant with 2 digits
    def __init__(self):
        super().__init__(PBT_REGEX3)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        result = super().process_match(match, description, db_cursor)

        if db_cursor and result.tenant_ref and not doubleCheckTenantRef(db_cursor, result.tenant_ref, description):
            tenant_ref = f"{match.group(1)}-{match.group(2)}-0{match.group(3)}"
            if not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                raise MatchValidationException("Failed to validate tenant reference")
            return MatchResult.match(result.property_ref, result.block_ref, tenant_ref)
        return result


class PBTRegex3SingleDigitBlockStrategy(RegexStrategy):
    # Match tenant with single digit block (e.g., 124-1-034)
    def __init__(self):
        super().__init__(re.compile(r"(?:^|\s+|,)(\d{3})-(\d{1})-(\d{2,3})\s?(?:DC)?(?:$|\s+|,|/)"))

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        result = super().process_match(match, description, db_cursor)

        if db_cursor and result.tenant_ref and not doubleCheckTenantRef(db_cursor, result.tenant_ref, description):
            # If initial validation fails, try padding the block to 2 digits
            property_ref = match.group(1)
            block_ref = match.group(2).zfill(2)  # "1" -> "01"
            tenant_ref = match.group(3).zfill(3) if len(match.group(3)) == 2 else match.group(3)  # Pad if 2 digits

            padded_tenant_ref = f"{property_ref}-{block_ref}-{tenant_ref}"
            if not doubleCheckTenantRef(db_cursor, padded_tenant_ref, description):
                raise MatchValidationException("Failed to validate tenant reference")
            return MatchResult.match(property_ref, block_ref, padded_tenant_ref)

        return result


class PBTRegex4Strategy(RegexStrategy):
    # Match property with 2 digits
    def __init__(self):
        super().__init__(PBT_REGEX4)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        result = super().process_match(match, description, db_cursor)

        if db_cursor and result.tenant_ref and not checkTenantExists(db_cursor, result.tenant_ref):
            property_ref = f"0{match.group(1)}"
            block_ref = f"{property_ref}-{match.group(2)}"
            tenant_ref = f"{block_ref}-{match.group(3)}"
            if not checkTenantExists(db_cursor, tenant_ref):
                raise MatchValidationException(f"Failed to validate tenant reference: tenant {tenant_ref} does not exist")
            return MatchResult.match(property_ref, block_ref, tenant_ref)
        return result


class ExcludeZSuffixStrategy(RegexStrategy):
    """Match properties that exclude Z suffix tenant references"""

    def __init__(self):
        super().__init__(PBT_REGEX)  # Use standard regex for these properties

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)
        block_ref = f"{property_ref}-{match.group(2)}"
        tenant_ref = f"{block_ref}-{match.group(3)}"

        # Only process properties that are in exclude Z suffix list
        if property_ref not in get_exclude_z_suffix_properties():
            return MatchResult.no_match()

        # Check if tenant reference ends with Z and return excluded match if it does
        if match.group(3).endswith("Z"):
            return MatchResult.excluded_match(property_ref, block_ref, tenant_ref)

        # If no Z suffix, allow processing to continue to other strategies (like RegexStrategy)
        return MatchResult.no_match()


class SpecialCaseStrategy(RegexStrategy):
    # Try to match property, block and tenant special cases - only 4-digit patterns
    def __init__(self):
        super().__init__(PBT_REGEX_SPECIAL_NARROW)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref: str | None = match.group(1)
        block_ref: str | None = f"{match.group(1)}-{match.group(2)}"
        tenant_ref: str | None = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

        # Only allow properties that are in special case list (4-digit patterns)
        if property_ref not in get_special_case_properties():
            raise MatchValidationException("Failed to validate special case property: property not in special cases list")

        if db_cursor:
            tenant_ref = removeDCReferencePostfix(tenant_ref) or tenant_ref  # Keep original if None
            if tenant_ref and not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                if property_ref and block_ref:
                    property_ref, block_ref, tenant_ref = correctKnownCommonErrors(property_ref, block_ref, tenant_ref)
                if tenant_ref and not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                    raise MatchValidationException("Failed to validate tenant reference")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class PBRegexStrategy(RegexStrategy):
    def __init__(self):
        super().__init__(PB_REGEX)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)
        block_ref = f"{match.group(1)}-{match.group(2)}"
        tenant_ref = None
        return MatchResult.match(property_ref, block_ref, tenant_ref)


class PTRegexStrategy(RegexStrategy):
    # Match property reference only
    def __init__(self):
        super().__init__(PT_REGEX)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)
        tenant_ref = match.group(2)  # Non-unique tenant ref, may be useful
        block_ref = "01"  # Null block indicates that the tenant and block can't be matched uniquely
        return MatchResult.match(property_ref, block_ref, tenant_ref)


class PRegexStrategy(RegexStrategy):
    def __init__(self):
        super().__init__(P_REGEX)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)
        block_ref, tenant_ref = None, None
        return MatchResult.match(property_ref, block_ref, tenant_ref)


class NoHyphenRegexStrategy(MatchingStrategy):
    def match(self, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        match = self._find_regex_match(description)
        if not match:
            return MatchResult.no_match()

        property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)

        if db_cursor and tenant_ref and not doubleCheckTenantRef(db_cursor, tenant_ref, description):
            if property_ref and block_ref:
                property_ref, block_ref, tenant_ref = correctKnownCommonErrors(property_ref, block_ref, tenant_ref)
            if tenant_ref and not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                raise MatchValidationException("Failed to validate tenant reference")
        return MatchResult.match(property_ref, block_ref, tenant_ref)

    def _find_regex_match(self, description: str) -> re.Match | None:
        """Try multiple regex patterns and return first match."""
        patterns = [PBT_REGEX_NO_HYPHENS, PBT_REGEX_NO_HYPHENS_SPECIAL_CASES, PBT_REGEX_NO_TERMINATING_SPACE, PBT_REGEX_NO_BEGINNING_SPACE]

        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return match
        return None


# class PostProcessStrategy(MatchingStrategy):
#     def match(self, description: str, db_cursor: Optional[sqlite3.Cursor]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
#         property_ref, block_ref, tenant_ref = super().match(description, db_cursor)
#         return postProcessPropertyBlockTenantRefs(property_ref, block_ref, tenant_ref)


# AlphaSuffixTenantStrategy can use RegexStrategy directly since it's just basic regex matching


class PropertyBlockWithCommercialPropertyStrategy(RegexStrategy):
    """Match property with COM references like 156-COM-001 and 144-01-COM"""

    def __init__(self):
        super().__init__(PBT_REGEX_COM_BLOCK)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. 156
        block_ref = f"{property_ref}-{match.group(2)}"  # e.g. 156-COM
        tenant_ref = f"{block_ref}-{match.group(3)}"  # e.g. 156-COM-001

        # Only allow properties that are configured as commercial properties
        if property_ref not in get_commercial_properties():
            raise MatchValidationException("Failed to validate commercial property: property not in commercial properties list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class PropertyBlockWithCommercialTenantStrategy(RegexStrategy):
    """Match property with COM tenant references like 144-01-COM"""

    def __init__(self):
        super().__init__(PBT_REGEX_COM_TENANT)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. 144
        # Swap groups 2 and 3: COM becomes the block, the number becomes the tenant
        block_ref = f"{property_ref}-{match.group(3)}"  # e.g. 144-COM
        tenant_ref = f"{block_ref}-{match.group(2)}"  # e.g. 144-COM-01

        # Only allow properties that are configured as commercial properties
        if property_ref not in get_commercial_properties():
            raise MatchValidationException("Failed to validate commercial property: property not in commercial properties list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class IndustrialEstateStrategy(RegexStrategy):
    """Match industrial estate properties with single-letter tenant references like 177-01-B"""

    def __init__(self):
        super().__init__(PBT_REGEX_INDUSTRIAL_ESTATE)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. 177
        block_ref = f"{property_ref}-{match.group(2)}"  # e.g. 177-01
        tenant_ref = f"{block_ref}-{match.group(3)}"  # e.g. 177-01-B

        # Only allow properties that are configured as industrial estate properties
        if property_ref not in get_industrial_estate_properties():
            raise MatchValidationException("Failed to validate industrial estate property: property not in industrial estate properties list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class DigitLetterSuffixStrategy(RegexStrategy):
    """Match properties with digit-letter suffix tenant references like 148-05-028E"""

    def __init__(self):
        super().__init__(PBT_REGEX_DIGIT_LETTER_SUFFIX)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. 148
        block_ref = f"{property_ref}-{match.group(2)}"  # e.g. 148-05
        tenant_ref = f"{block_ref}-{match.group(3)}"  # e.g. 148-05-028E

        # Only allow properties that are configured for digit-letter suffix patterns
        if property_ref not in get_digit_letter_suffix_properties():
            raise MatchValidationException("Failed to validate digit-letter suffix property: property not in digit-letter suffix properties list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class LetterDigitLetterStrategy(RegexStrategy):
    """Match properties with digit-letter-digit tenant references like 094-01-0A1"""

    def __init__(self):
        super().__init__(PBT_REGEX_LETTER_DIGIT_LETTER)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. 094
        block_ref = f"{property_ref}-{match.group(2)}"  # e.g. 094-01
        tenant_ref = f"{block_ref}-{match.group(3)}"  # e.g. 094-01-0A1

        # Only allow properties that are configured for letter-digit-letter patterns
        if property_ref not in get_letter_digit_letter_properties():
            raise MatchValidationException("Failed to validate letter-digit-letter property: property not in letter-digit-letter properties list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class DoubleZeroLetterStrategy(RegexStrategy):
    """Match properties with 00X tenant references like 134-01-00A"""

    def __init__(self):
        super().__init__(PBT_REGEX_DOUBLE_ZERO_LETTER)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. 134
        block_ref = f"{property_ref}-{match.group(2)}"  # e.g. 134-01
        tenant_ref = f"{block_ref}-{match.group(3)}"  # e.g. 134-01-00A

        # Only allow properties that are configured for double-zero-letter patterns
        if property_ref not in get_double_zero_letter_properties():
            raise MatchValidationException("Failed to validate double-zero-letter property: property not in double-zero-letter properties list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class ThreeLetterCodeStrategy(RegexStrategy):
    """Match properties with three-letter code tenant references like 166-01-FFF"""

    def __init__(self):
        super().__init__(PBT_REGEX_THREE_LETTER_CODE)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. 166
        block_ref = f"{property_ref}-{match.group(2)}"  # e.g. 166-01
        tenant_ref = f"{block_ref}-{match.group(3)}"  # e.g. 166-01-FFF

        # Only allow properties that are configured for three-letter code patterns
        if property_ref not in get_three_letter_code_properties():
            raise MatchValidationException("Failed to validate three-letter code property: property not in three-letter code properties list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class TwoLetterCodeStrategy(RegexStrategy):
    """Match properties with two-letter code tenant references like 161-01-GH"""

    def __init__(self):
        super().__init__(PBT_REGEX_TWO_LETTER_CODE)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. 161
        block_ref = f"{property_ref}-{match.group(2)}"  # e.g. 161-01
        tenant_ref = f"{block_ref}-{match.group(3)}"  # e.g. 161-01-GH

        # Only allow properties that are configured for two-letter code patterns
        if property_ref not in get_two_letter_code_properties():
            raise MatchValidationException("Failed to validate two-letter code property: property not in two-letter code properties list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class CatchRemainderStrategy(RegexStrategy):
    """Catch any remaining patterns that specific strategies missed - uses broad regex as safety net"""

    def __init__(self):
        super().__init__(PBT_REGEX_CATCH_REMAINDER)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)
        block_ref = f"{property_ref}-{match.group(2)}"
        tenant_ref = f"{block_ref}-{match.group(3)}"

        # This strategy accepts any property - it's a true catch-all fallback
        # No property validation to ensure it catches anything the specific strategies missed
        return MatchResult.match(property_ref, block_ref, tenant_ref)


class AlphanumericPropertyStrategy(RegexStrategy):
    """Match alphanumeric property references like 059A-01-001"""

    def __init__(self):
        super().__init__(PBT_REGEX_ALPHANUMERIC)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. "059A"
        block_ref = f"{property_ref}-{match.group(2)}"  # e.g. "059A-01"
        tenant_ref = f"{block_ref}-{match.group(3)}"  # e.g. "059A-01-001"

        # Only allow known alphanumeric properties from config
        if property_ref not in get_alphanumeric_properties():
            raise MatchValidationException(f"Alphanumeric property '{property_ref}' not in allowed list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class AlphanumericPropertyNoHyphensStrategy(RegexStrategy):
    """Match alphanumeric property references without hyphens like '059A 01 001'"""

    def __init__(self):
        super().__init__(PBT_REGEX_ALPHANUMERIC_NO_HYPHENS)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. "059A"
        block_ref = f"{property_ref}-{match.group(2)}"  # e.g. "059A-01"
        tenant_ref = f"{block_ref}-{match.group(3)}"  # e.g. "059A-01-001"

        # Only allow known alphanumeric properties from config
        if property_ref not in get_alphanumeric_properties():
            raise MatchValidationException(f"Alphanumeric property '{property_ref}' not in allowed list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class AlphanumericPropertyForwardSlashStrategy(RegexStrategy):
    """Match alphanumeric property references with forward slashes like '059A/01/001'"""

    def __init__(self):
        super().__init__(PBT_REGEX_ALPHANUMERIC_FWD_SLASHES)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. "059A"
        block_ref = f"{property_ref}-{match.group(2)}"  # e.g. "059A-01"
        tenant_ref = f"{block_ref}-{match.group(3)}"  # e.g. "059A-01-001"

        # Only allow known alphanumeric properties from config
        if property_ref not in get_alphanumeric_properties():
            raise MatchValidationException(f"Alphanumeric property '{property_ref}' not in allowed list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class AlphanumericPropertyBlockStrategy(RegexStrategy):
    """Match alphanumeric property-block references like '059A-01'"""

    def __init__(self):
        super().__init__(PB_REGEX_ALPHANUMERIC)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. "059A"
        block_ref = f"{property_ref}-{match.group(2)}"  # e.g. "059A-01"
        tenant_ref = None

        # Only allow known alphanumeric properties from config
        if property_ref not in get_alphanumeric_properties():
            raise MatchValidationException(f"Alphanumeric property '{property_ref}' not in allowed list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class AlphanumericPropertyOnlyStrategy(RegexStrategy):
    """Match alphanumeric property references only like '059A'"""

    def __init__(self):
        super().__init__(P_REGEX_ALPHANUMERIC)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref = match.group(1)  # e.g. "059A"
        block_ref = None
        tenant_ref = None

        # Only allow known alphanumeric properties from config
        if property_ref not in get_alphanumeric_properties():
            raise MatchValidationException(f"Alphanumeric property '{property_ref}' not in allowed list")

        return MatchResult.match(property_ref, block_ref, tenant_ref)


class PropertyBlockTenantRefMatcher:
    def __init__(self):
        self.strategies: list[MatchingStrategy] = []
        self.log_file = None
        self._is_test_environment = self._detect_test_environment()

        # Determine if CSV logging should be enabled
        should_log_csv = self._should_enable_csv_logging()

        if should_log_csv:
            self.log_file = get_wpp_ref_matcher_log_file(datetime.now())
            self._setup_log_file()

    def _should_enable_csv_logging(self) -> bool:
        """Determine if CSV logging should be enabled based on environment and config."""
        # Tests always log CSV
        if self._is_test_environment:
            return True

        # Production (web and console) follow config setting
        config = get_config()
        return config.get("LOGS", {}).get("REF_MATCHER_CSV_ENABLED", True)

    def _detect_test_environment(self):
        """Detect if we're running in a test environment."""
        # Check if pytest is running
        return "pytest" in sys.modules or "unittest" in sys.modules

    def enable_logging(self, log_file_path=None):
        """Enable CSV logging for this matcher instance."""
        if log_file_path:
            self.log_file = Path(log_file_path)
        elif not self.log_file:
            # Use default log file path if none provided
            self.log_file = get_wpp_ref_matcher_log_file(datetime.now())
        self._setup_log_file()

    def _setup_log_file(self):
        if self.log_file and not self.log_file.exists():
            # Ensure the parent directory exists
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["description", "property_ref", "block_ref", "tenant_ref", "strategy"])

    def add_strategy(self, strategy: MatchingStrategy):
        self.strategies.append(strategy)

    def match(self, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        result = self.match_result(description, db_cursor)
        return result.to_tuple()

    def match_result(self, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        """Internal method that returns MatchResult instead of tuple."""
        for strategy in self.strategies:
            try:
                result = strategy.match(description, db_cursor)
                if result.matched:
                    match_data = MatchLogData(description, result.property_ref, result.block_ref, result.tenant_ref, strategy.name())
                    self._log_match(match_data)
                    return result
            except MatchValidationException:
                # Exception raised when a strategy matches but fails post-match validation, break out of the loop and don't try any more strategies
                match_data = MatchLogData(description, None, None, None, strategy.name())
                self._log_match(match_data)
                return MatchResult.no_match()

        match_data = MatchLogData(description, None, None, None, "NoMatch")
        self._log_match(match_data)
        return MatchResult.no_match()

    def _log_match(self, match_data: MatchLogData):
        # Always collect data for potential web/output handler use
        if not hasattr(self, "collected_matches"):
            self.collected_matches = []
        self.collected_matches.append(match_data)

        # Only log to CSV file if we have a log file configured (console app behavior)
        if self.log_file is not None:
            # Ensure the file exists with headers before appending
            if not self.log_file.exists():
                self._setup_log_file()
            with open(self.log_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([match_data.description, match_data.property_ref, match_data.block_ref, match_data.tenant_ref, match_data.strategy_name])

    def export_collected_data(self, output_handler):
        """Export collected ref_matcher data to the provided output handler."""
        if hasattr(self, "collected_matches") and self.collected_matches:
            import pandas as pd

            # Convert collected data to DataFrame
            data_rows = []
            for match in self.collected_matches:
                data_rows.append(
                    {
                        "Transaction Description": match.description,
                        "Property Ref": match.property_ref or "",
                        "Block Ref": match.block_ref or "",
                        "Tenant Ref": match.tenant_ref or "",
                        "Strategy Used": match.strategy_name,
                    }
                )

            # Data is already saved to CSV via self.log_file when CSV logging is enabled
            # No need to export to output_handler as ref_matcher logs can be very large for web interface

    def clear_collected_data(self):
        """Clear collected data (useful for testing or reset)."""
        if hasattr(self, "collected_matches"):
            self.collected_matches = []


def checkForIrregularTenantRefInDatabase(reference: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
    """Look for known irregular transaction refs which we know some tenants use."""
    if db_cursor:
        tenant_ref = get_single_value(db_cursor, SELECT_IRREGULAR_TRANSACTION_TENANT_REF_SQL, (reference,))
        if tenant_ref:
            return getPropertyBlockAndTenantRefs(tenant_ref)  # Parse tenant reference
        # else:
        #    transaction_ref_data = get_data(db_cursor, SELECT_ALL_IRREGULAR_TRANSACTION_REFS_SQL)
        #    for tenant_ref, transaction_ref_pattern in transaction_ref_data:
        #        pass
    return MatchResult.no_match()


# Module-level matcher instance to avoid creating multiple log files
_matcher_instance = None


def _get_matcher() -> PropertyBlockTenantRefMatcher:
    """Get the singleton matcher instance."""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = PropertyBlockTenantRefMatcher()
        _matcher_instance.add_strategy(IrregularTenantRefStrategy())
        _matcher_instance.add_strategy(ExcludeZSuffixStrategy())  # For properties 020, 022, 039 with Z-suffix exclusion - check before general RegexStrategy
        # Add alphanumeric property strategies early for priority
        _matcher_instance.add_strategy(AlphanumericPropertyStrategy())  # For alphanumeric properties like 059A-01-001
        _matcher_instance.add_strategy(AlphanumericPropertyForwardSlashStrategy())  # For alphanumeric properties like 059A/01/001
        _matcher_instance.add_strategy(AlphanumericPropertyNoHyphensStrategy())  # For alphanumeric properties like '059A 01 001'
        _matcher_instance.add_strategy(RegexStrategy(PBT_REGEX))
        _matcher_instance.add_strategy(RegexDoubleCheckStrategy(PBT_REGEX_FWD_SLASHES))
        _matcher_instance.add_strategy(RegexDoubleCheckStrategy(PBT_REGEX2))  # Match tenant with spaces between hyphens
        _matcher_instance.add_strategy(PBTRegex3Strategy())
        _matcher_instance.add_strategy(PBTRegex3SingleDigitBlockStrategy())  # For single digit blocks like 124-1-034
        _matcher_instance.add_strategy(PBTRegex4Strategy())
        # Add specific strategies before SpecialCaseStrategy to get priority
        _matcher_instance.add_strategy(PropertyBlockWithCommercialPropertyStrategy())  # For commercial property patterns e.g. 156-COM-001
        _matcher_instance.add_strategy(PropertyBlockWithCommercialTenantStrategy())  # For commercial tenant patterns e.g. 144-01-COM
        _matcher_instance.add_strategy(IndustrialEstateStrategy())  # For industrial estate patterns e.g. 177-01-B
        _matcher_instance.add_strategy(DigitLetterSuffixStrategy())  # For digit-letter suffix patterns e.g. 148-05-028E
        _matcher_instance.add_strategy(LetterDigitLetterStrategy())  # For letter-digit-letter patterns e.g. 094-01-0A1
        _matcher_instance.add_strategy(DoubleZeroLetterStrategy())  # For double-zero-letter patterns e.g. 134-01-00A
        _matcher_instance.add_strategy(ThreeLetterCodeStrategy())  # For three-letter code patterns e.g. 166-01-FFF
        _matcher_instance.add_strategy(TwoLetterCodeStrategy())  # For two-letter code patterns e.g. 161-01-GH
        _matcher_instance.add_strategy(SpecialCaseStrategy())
        _matcher_instance.add_strategy(CatchRemainderStrategy())  # Safety net for any patterns missed by specific strategies
        _matcher_instance.add_strategy(AlphanumericPropertyBlockStrategy())  # For alphanumeric property-block like 059A-01
        # _matcher_instance.add_strategy(PTRegexStrategy())
        _matcher_instance.add_strategy(NoHyphenRegexStrategy())
        _matcher_instance.add_strategy(AlphanumericPropertyOnlyStrategy())  # For alphanumeric property-only like 059A
        # New strategies for 2025-08-04 scenario tenant reference formats - added at end
        _matcher_instance.add_strategy(RegexStrategy(PBT_REGEX_ALPHA_SUFFIX))  # For 059-01-001A patterns
        # General fallback strategies - try these last as they are most general
        _matcher_instance.add_strategy(PBRegexStrategy())  # For property-block patterns like 020-01
        _matcher_instance.add_strategy(PRegexStrategy())  # For property-only patterns like 020
    return _matcher_instance


def _reset_matcher():
    """Reset the singleton matcher instance. Used for test isolation."""
    global _matcher_instance
    _matcher_instance = None


def getPropertyBlockAndTenantRefs(reference: str, db_cursor: sqlite3.Cursor | None = None) -> MatchResult:
    """Parse property, block and tenant references from a transaction description."""
    if not isinstance(reference, str):
        return MatchResult.no_match()

    description = str(reference).strip()
    # if "MEDHURST K M 10501001 RP4652285818999300" in description:
    #     pass

    matcher = _get_matcher()
    result = matcher.match_result(description, db_cursor)
    if result.matched:
        if result.is_excluded():
            # Excluded matches should be treated as no_match for calling code
            return MatchResult.no_match()
        else:
            # Normal matches get post-processed
            property_ref, block_ref, tenant_ref = postProcessPropertyBlockTenantRefs(result.property_ref, result.block_ref, result.tenant_ref)
            return MatchResult.match(property_ref, block_ref, tenant_ref)
    else:
        return MatchResult.no_match()
