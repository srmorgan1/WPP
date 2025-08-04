import re
import sqlite3
from abc import ABC, abstractmethod

from wpp.db import get_single_value
from wpp.utils import getLongestCommonSubstring

#
# SQL
#
SELECT_TENANT_NAME_SQL = "SELECT tenant_name FROM Tenants WHERE tenant_ref = ?;"
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


def checkTenantExists(db_cursor: sqlite3.Cursor, tenant_ref: str) -> str | None:
    tenant_name = get_single_value(db_cursor, SELECT_TENANT_NAME_SQL, (tenant_ref,))
    return tenant_name


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

    if tenant_name:
        lcss = getLongestCommonSubstring(tnm, trf)
        # Assume that if the transaction reference has a substring matching
        # one in the tenant name of >= 4 chars, then this is a match.
        return len(lcss) >= 4
    else:
        return False


def removeDCReferencePostfix(tenant_ref: str | None) -> str | None:
    # Remove 'DC' from parsed tenant references paid by debit card
    if tenant_ref is not None and tenant_ref.endswith("DC"):
        tenant_ref = tenant_ref[:-2].strip()
    return tenant_ref


def correctKnownCommonErrors(property_ref: str, block_ref: str, tenant_ref: str | None) -> tuple[str, str, str | None]:
    # Correct known errors in the tenant payment references
    if property_ref == "094" and tenant_ref is not None and tenant_ref[-3] == "O":
        tenant_ref = tenant_ref[:-3] + "0" + tenant_ref[-2:]
    return property_ref, block_ref, tenant_ref


def recodeSpecialPropertyReferenceCases(property_ref: str, block_ref: str, tenant_ref: str | None) -> tuple[str, str, str | None]:
    if property_ref == "020" and block_ref == "020-03":
        # Block 020-03 belongs to a different property group, call this 020A.
        property_ref = "020A"
    elif property_ref == "064" and block_ref == "064-01":
        property_ref = "064A"
    return property_ref, block_ref, tenant_ref


def recodeSpecialBlockReferenceCases(property_ref: str, block_ref: str, tenant_ref: str | None) -> tuple[str, str, str | None]:
    if property_ref == "101" and block_ref == "101-02":
        # Block 101-02 is wrong, change this to 101-01
        block_ref = "101-01"
        tenant_ref = tenant_ref.replace("101-02", "101-01") if tenant_ref is not None else tenant_ref
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
    tenant_name = checkTenantExists(db_cursor, tenant_ref)
    if tenant_name:
        return matchTransactionRef(tenant_name, reference)
    else:
        return False


def postProcessPropertyBlockTenantRefs(property_ref: str | None, block_ref: str | None, tenant_ref: str | None) -> tuple[str | None, str | None, str | None]:
    # Ignore some property and tenant references, and recode special cases
    # e.g. Block 020-03 belongs to a different property than the other 020-xx blocks.
    if (tenant_ref is not None and ("Z" in tenant_ref or "Y" in tenant_ref)) or (property_ref is not None and property_ref.isnumeric() and int(property_ref) >= 900):
        return None, None, None
    property_ref, block_ref, tenant_ref = recodeSpecialPropertyReferenceCases(property_ref, block_ref, tenant_ref)
    property_ref, block_ref, tenant_ref = recodeSpecialBlockReferenceCases(property_ref, block_ref, tenant_ref)
    return property_ref, block_ref, tenant_ref


class MatchingStrategy(ABC):
    @abstractmethod
    def match(self, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        pass


class MatchValidationException(Exception):
    """Raise when a matching strategy matches but fails validation"""


class IrregularTenantRefStrategy(MatchingStrategy):
    def match(self, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        property_ref, block_ref, tenant_ref = checkForIrregularTenantRefInDatabase(description, db_cursor)
        if property_ref and block_ref and tenant_ref:
            return property_ref, block_ref, tenant_ref
        return None, None, None


class RegexStrategy(MatchingStrategy):
    def __init__(self, regex: re.Pattern):
        self.regex = regex

    def match(self, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        match = re.search(self.regex, description)
        if match:
            return self.process_match(match, description, db_cursor)
        else:
            return None, None, None

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        # This was originally a check for the tenant reference in the database with PBT_REGEX (commented out in old code)
        # if db_cursor and not checkTenantExists(db_cursor, tenant_ref):
        #    return None, None, None
        property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
        # if db_cursor and not checkTenantExists(db_cursor, tenant_ref):
        #    raise MatchValidationException("Failed to validate tenant reference")
        return property_ref, block_ref, tenant_ref


class RegexDoubleCheckStrategy(RegexStrategy):
    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        property_ref, block_ref, tenant_ref = super().process_match(match, description, db_cursor)

        if db_cursor and not doubleCheckTenantRef(db_cursor, tenant_ref, description):
            raise MatchValidationException("Failed to validate tenant reference")
        return property_ref, block_ref, tenant_ref


class PBTRegex3Strategy(RegexStrategy):
    # Match tenant with 2 digits
    def __init__(self):
        super().__init__(PBT_REGEX3)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        property_ref, block_ref, tenant_ref = super().process_match(match, description, db_cursor)

        if db_cursor and not doubleCheckTenantRef(db_cursor, tenant_ref, description):
            tenant_ref = f"{match.group(1)}-{match.group(2)}-0{match.group(3)}"
            if not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                raise MatchValidationException("Failed to validate tenant reference")
        return property_ref, block_ref, tenant_ref


class PBTRegex4Strategy(RegexStrategy):
    # Match property with 2 digits
    def __init__(self):
        super().__init__(PBT_REGEX4)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        property_ref, block_ref, tenant_ref = super().process_match(match, description, db_cursor)

        if db_cursor and not checkTenantExists(db_cursor, tenant_ref):
            property_ref = f"0{match.group(1)}"
            block_ref = f"{property_ref}-{match.group(2)}"
            tenant_ref = f"{block_ref}-{match.group(3)}"
            if not checkTenantExists(db_cursor, tenant_ref):
                raise MatchValidationException(f"Failed to validate tenant reference: tenant {tenant_ref} does not exist")
        return property_ref, block_ref, tenant_ref


class SpecialCaseStrategy(RegexStrategy):
    # Try to match property, block and tenant special cases
    def __init__(self):
        super().__init__(PBT_REGEX_SPECIAL_CASES)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        property_ref = match.group(1)
        block_ref = f"{match.group(1)}-{match.group(2)}"
        tenant_ref = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        if db_cursor:
            tenant_ref = removeDCReferencePostfix(tenant_ref)
            if not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                property_ref, block_ref, tenant_ref = correctKnownCommonErrors(property_ref, block_ref, tenant_ref)
                if not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                    raise MatchValidationException("Failed to validate tenant reference")
        elif not (
            (
                property_ref
                in [
                    "093",
                    "094",
                    "095",
                    "096",
                    "099",
                    "124",
                    "132",
                    "133",
                    "134",
                ]
            )
            or (property_ref in ["020", "022", "039", "053", "064"] and match.group(3)[-1] != "Z")
        ):
            raise MatchValidationException("Failed to validate tenant reference: the property is not in the special cases lists")
        return property_ref, block_ref, tenant_ref


class PBRegexStrategy(RegexStrategy):
    def __init__(self):
        super().__init__(PB_REGEX)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        property_ref = match.group(1)
        block_ref = f"{match.group(1)}-{match.group(2)}"
        tenant_ref = None
        return property_ref, block_ref, tenant_ref


class PTRegexStrategy(RegexStrategy):
    # Match property reference only
    def __init__(self):
        super().__init__(PT_REGEX)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        property_ref = match.group(1)
        tenant_ref = match.group(2)  # Non-unique tenant ref, may be useful
        block_ref = "01"  # Null block indicates that the tenant and block can't be matched uniquely
        return property_ref, block_ref, tenant_ref


class PRegexStrategy(RegexStrategy):
    def __init__(self):
        super().__init__(P_REGEX)

    def process_match(self, match: re.Match, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        property_ref = match.group(1)
        block_ref, tenant_ref = None, None
        return property_ref, block_ref, tenant_ref


class NoHyphenRegexStrategy(MatchingStrategy):
    def match(self, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        match = (
            re.search(PBT_REGEX_NO_HYPHENS, description)
            or re.search(PBT_REGEX_NO_HYPHENS_SPECIAL_CASES, description)
            or re.search(PBT_REGEX_NO_TERMINATING_SPACE, description)
            or re.search(PBT_REGEX_NO_BEGINNING_SPACE, description)
        )
        if match:
            property_ref, block_ref, tenant_ref = getPropertyBlockAndTenantRefsFromRegexMatch(match)
            if db_cursor and not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                property_ref, block_ref, tenant_ref = correctKnownCommonErrors(property_ref, block_ref, tenant_ref)
                if not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                    raise MatchValidationException("Failed to validate tenant reference")
            return property_ref, block_ref, tenant_ref

        return None, None, None


# class PostProcessStrategy(MatchingStrategy):
#     def match(self, description: str, db_cursor: Optional[sqlite3.Cursor]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
#         property_ref, block_ref, tenant_ref = super().match(description, db_cursor)
#         return postProcessPropertyBlockTenantRefs(property_ref, block_ref, tenant_ref)


class PropertyBlockTenantRefMatcher:
    def __init__(self):
        self.strategies: list[MatchingStrategy] = []

    def add_strategy(self, strategy: MatchingStrategy):
        self.strategies.append(strategy)

    def match(self, description: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
        try:
            for strategy in self.strategies:
                property_ref, block_ref, tenant_ref = strategy.match(description, db_cursor)
                if property_ref or block_ref or tenant_ref:
                    return property_ref, block_ref, tenant_ref
        except MatchValidationException:
            # Exception raised when a strategy matches but fails post-match validation, break out of the loop and don't try any more strategies
            pass

        return None, None, None


def checkForIrregularTenantRefInDatabase(reference: str, db_cursor: sqlite3.Cursor | None) -> tuple[str | None, str | None, str | None]:
    # Look for known irregular transaction refs which we know some tenants use
    if db_cursor:
        tenant_ref = get_single_value(db_cursor, SELECT_IRREGULAR_TRANSACTION_TENANT_REF_SQL, (reference,))
        if tenant_ref:
            return getPropertyBlockAndTenantRefs(tenant_ref)  # Parse tenant reference
        # else:
        #    transaction_ref_data = get_data(db_cursor, SELECT_ALL_IRREGULAR_TRANSACTION_REFS_SQL)
        #    for tenant_ref, transaction_ref_pattern in transaction_ref_data:
        #        pass
    return None, None, None


def getPropertyBlockAndTenantRefs(reference: str, db_cursor: sqlite3.Cursor | None = None) -> tuple[str | None, str | None, str | None]:
    if not isinstance(reference, str):
        return None, None, None

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

    property_ref, block_ref, tenant_ref = matcher.match(description, db_cursor)
    return postProcessPropertyBlockTenantRefs(property_ref, block_ref, tenant_ref)
