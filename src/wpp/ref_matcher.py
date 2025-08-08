from __future__ import annotations

import csv
import re
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass

from wpp.config import get_wpp_ref_matcher_log_file
from wpp.constants import (
    MINIMUM_TENANT_NAME_MATCH_LENGTH,
    DEBIT_CARD_SUFFIX,
    PROPERTY_094_ERROR_CHAR,
    PROPERTY_094_CORRECTION_POSITION,
    MIN_TENANT_REF_LENGTH_FOR_ERROR_CORRECTION,
    SPECIAL_CASE_PROPERTIES,
    CONDITIONAL_SPECIAL_CASE_PROPERTIES,
    SPECIAL_PROPERTY_RECODING,
    SPECIAL_BLOCK_RECODING,
    EXCLUDED_TENANT_REF_CHARACTERS,
    MINIMUM_VALID_PROPERTY_REF,
)
from wpp.db import get_single_value, checkTenantExists, getTenantName
from wpp.data_classes import MatchLogData
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

    @classmethod
    def no_match(cls) -> MatchResult:
        """Create a MatchResult representing no match found."""
        return cls(matched=False)

    @classmethod
    def match(cls, property_ref: str | None, block_ref: str | None, tenant_ref: str | None) -> MatchResult:
        """Create a MatchResult representing a successful match."""
        return cls(property_ref=property_ref, block_ref=block_ref, tenant_ref=tenant_ref, matched=True)

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
PBT_REGEX = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d)-(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX2 = re.compile(r"(?:^|\s+|,)(\d\d\d)\s-\s(\d\d)\s-\s(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX3 = re.compile(r"(?:^|\s+|,)(\d\d\d)-0?(\d\d)-(\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX4 = re.compile(r"(?:^|\s+|,)(\d\d)-0?(\d\d)-(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_NO_TERMINATING_SPACE = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d)-(\d\d\d)(?:$|\s*|,|/)")
PBT_REGEX_NO_BEGINNING_SPACE = re.compile(r"(?:^|\s*|,)(\d\d\d)-(\d\d)-(\d\d\d)(?:$|\s+|,|/)")
PBT_REGEX_SPECIAL_CASES = re.compile(
    r"(?:^|\s+|,|\.)(\d\d\d)-{1,2}0?(\d\d)-{1,2}(\w{2,5})\s?(?:DC)?(?:$|\s+|,|/)",
    re.ASCII,
)
PBT_REGEX_NO_HYPHENS = re.compile(r"(?:^|\s+|,)(\d\d\d)\s{0,2}0?(\d\d)\s{0,2}(\d\d\d)(?:$|\s+|,|/)")
PBT_REGEX_NO_HYPHENS_SPECIAL_CASES = re.compile(r"(?:^|\s+|,)(\d\d\d)\s{0,2}0?(\d\d)\s{0,2}(\w{3})(?:$|\s+|,|/)", re.ASCII)
PBT_REGEX_FWD_SLASHES = re.compile(r"(?:^|\s+|,)(\d\d\d)/0?(\d\d)/(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
PT_REGEX = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d\d)(?:$|\s+|,|/)")
PB_REGEX = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d)(?:$|\s+|,|/)")
P_REGEX = re.compile(r"(?:^|\s+)(\d\d\d)(?:$|\s+)")


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


class SpecialCaseStrategy(RegexStrategy):
    # Try to match property, block and tenant special cases
    def __init__(self):
        super().__init__(PBT_REGEX_SPECIAL_CASES)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> MatchResult:
        property_ref: str | None = match.group(1)
        block_ref: str | None = f"{match.group(1)}-{match.group(2)}"
        tenant_ref: str | None = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        if db_cursor:
            tenant_ref = removeDCReferencePostfix(tenant_ref) or tenant_ref  # Keep original if None
            if tenant_ref and not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                if property_ref and block_ref:
                    property_ref, block_ref, tenant_ref = correctKnownCommonErrors(property_ref, block_ref, tenant_ref)
                if tenant_ref and not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                    raise MatchValidationException("Failed to validate tenant reference")
        elif not ((property_ref in SPECIAL_CASE_PROPERTIES) or (property_ref in CONDITIONAL_SPECIAL_CASE_PROPERTIES and match.group(3)[-1] != "Z")):
            raise MatchValidationException("Failed to validate tenant reference: the property is not in the special cases lists")
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


class PropertyBlockTenantRefMatcher:
    def __init__(self):
        self.strategies: list[MatchingStrategy] = []
        self.log_file = get_wpp_ref_matcher_log_file()
        self._setup_log_file()

    def _setup_log_file(self):
        if not self.log_file.exists():
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
        with open(self.log_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([match_data.description, match_data.property_ref, match_data.block_ref, match_data.tenant_ref, match_data.strategy_name])


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


def getPropertyBlockAndTenantRefs(reference: str, db_cursor: sqlite3.Cursor | None = None) -> MatchResult:
    """Parse property, block and tenant references from a transaction description."""
    if not isinstance(reference, str):
        return MatchResult.no_match()

    description = str(reference).strip()
    # if "MEDHURST K M 10501001 RP4652285818999300" in description:
    #     pass

    matcher = PropertyBlockTenantRefMatcher()
    matcher.add_strategy(IrregularTenantRefStrategy())
    matcher.add_strategy(RegexStrategy(PBT_REGEX))
    matcher.add_strategy(RegexDoubleCheckStrategy(PBT_REGEX_FWD_SLASHES))
    matcher.add_strategy(RegexDoubleCheckStrategy(PBT_REGEX2))  # Match tenant with spaces between hyphens
    matcher.add_strategy(PBTRegex3Strategy())
    matcher.add_strategy(PBTRegex4Strategy())
    matcher.add_strategy(SpecialCaseStrategy())
    matcher.add_strategy(PBRegexStrategy())
    # matcher.add_strategy(PTRegexStrategy())
    matcher.add_strategy(NoHyphenRegexStrategy())
    # matcher.add_strategy(PRegexStrategy())

    result = matcher.match_result(description, db_cursor)
    if result.matched:
        property_ref, block_ref, tenant_ref = postProcessPropertyBlockTenantRefs(result.property_ref, result.block_ref, result.tenant_ref)
        return MatchResult.match(property_ref, block_ref, tenant_ref)
    else:
        return MatchResult.no_match()
