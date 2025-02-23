from abc import ABC, abstractmethod
import re
import sqlite3
from typing import Optional, Tuple, List

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
PBT_REGEX2 = re.compile(
    r"(?:^|\s+|,)(\d\d\d)\s-\s(\d\d)\s-\s(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)"
)
PBT_REGEX3 = re.compile(r"(?:^|\s+|,)(\d\d\d)-0?(\d\d)-(\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX4 = re.compile(r"(?:^|\s+|,)(\d\d)-0?(\d\d)-(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)")
PBT_REGEX_NO_TERMINATING_SPACE = re.compile(
    r"(?:^|\s+|,)(\d\d\d)-(\d\d)-(\d\d\d)(?:$|\s*|,|/)"
)
PBT_REGEX_NO_BEGINNING_SPACE = re.compile(
    r"(?:^|\s*|,)(\d\d\d)-(\d\d)-(\d\d\d)(?:$|\s+|,|/)"
)
PBT_REGEX_SPECIAL_CASES = re.compile(
    r"(?:^|\s+|,|\.)(\d\d\d)-{1,2}0?(\d\d)-{1,2}(\w{2,5})\s?(?:DC)?(?:$|\s+|,|/)",
    re.ASCII,
)
PBT_REGEX_NO_HYPHENS = re.compile(
    r"(?:^|\s+|,)(\d\d\d)\s{0,2}0?(\d\d)\s{0,2}(\d\d\d)(?:$|\s+|,|/)"
)
PBT_REGEX_NO_HYPHENS_SPECIAL_CASES = re.compile(
    r"(?:^|\s+|,)(\d\d\d)\s{0,2}0?(\d\d)\s{0,2}(\w{3})(?:$|\s+|,|/)", re.ASCII
)
PBT_REGEX_FWD_SLASHES = re.compile(
    r"(?:^|\s+|,)(\d\d\d)/0?(\d\d)/(\d\d\d)\s?(?:DC)?(?:$|\s+|,|/)"
)
PT_REGEX = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d\d)(?:$|\s+|,|/)")
PB_REGEX = re.compile(r"(?:^|\s+|,)(\d\d\d)-(\d\d)(?:$|\s+|,|/)")
P_REGEX = re.compile(r"(?:^|\s+)(\d\d\d)(?:$|\s+)")


def checkTenantExists(db_cursor: sqlite3.Cursor, tenant_ref: str) -> Optional[str]:
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


def removeDCReferencePostfix(tenant_ref: Optional[str]) -> Optional[str]:
    # Remove 'DC' from parsed tenant references paid by debit card
    if tenant_ref is not None and tenant_ref[-2:] == "DC":
        tenant_ref = tenant_ref[:-2].strip()
    return tenant_ref


def correctKnownCommonErrors(
    property_ref: str, block_ref: str, tenant_ref: Optional[str]
) -> Tuple[str, str, Optional[str]]:
    # Correct known errors in the tenant payment references
    if property_ref == "094" and tenant_ref is not None and tenant_ref[-3] == "O":
        tenant_ref = tenant_ref[:-3] + "0" + tenant_ref[-2:]
    return property_ref, block_ref, tenant_ref


def recodeSpecialPropertyReferenceCases(
    property_ref: str, block_ref: str, tenant_ref: Optional[str]
) -> Tuple[str, str, Optional[str]]:
    if property_ref == "020" and block_ref == "020-03":
        # Block 020-03 belongs to a different property group, call this 020A.
        property_ref = "020A"
    elif property_ref == "064" and block_ref == "064-01":
        property_ref = "064A"
    return property_ref, block_ref, tenant_ref


def recodeSpecialBlockReferenceCases(
    property_ref: str, block_ref: str, tenant_ref: Optional[str]
) -> Tuple[str, str, Optional[str]]:
    if property_ref == "101" and block_ref == "101-02":
        # Block 101-02 is wrong, change this to 101-01
        block_ref = "101-01"
        tenant_ref = (
            tenant_ref.replace("101-02", "101-01")
            if tenant_ref is not None
            else tenant_ref
        )
    return property_ref, block_ref, tenant_ref


def getPropertyBlockAndTenantRefsFromRegexMatch(
    match: re.Match,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    property_ref, block_ref, tenant_ref = None, None, None
    if match:
        property_ref = match.group(1)
        block_ref = "{}-{}".format(match.group(1), match.group(2))
        tenant_ref = "{}-{}-{}".format(match.group(1), match.group(2), match.group(3))
    return property_ref, block_ref, tenant_ref


def doubleCheckTenantRef(
    db_cursor: sqlite3.Cursor, tenant_ref: str, reference: str
) -> bool:
    tenant_name = checkTenantExists(db_cursor, tenant_ref)
    if tenant_name:
        return matchTransactionRef(tenant_name, reference)
    else:
        return False


def postProcessPropertyBlockTenantRefs(
    property_ref: Optional[str], block_ref: Optional[str], tenant_ref: Optional[str]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # Ignore some property and tenant references, and recode special cases
    # e.g. Block 020-03 belongs to a different property than the other 020-xx blocks.
    if tenant_ref is not None and ("Z" in tenant_ref or "Y" in tenant_ref):
        return None, None, None
    elif (
        property_ref is not None
        and property_ref.isnumeric()
        and int(property_ref) >= 900
    ):
        return None, None, None
    property_ref, block_ref, tenant_ref = recodeSpecialPropertyReferenceCases(
        property_ref, block_ref, tenant_ref
    )
    property_ref, block_ref, tenant_ref = recodeSpecialBlockReferenceCases(
        property_ref, block_ref, tenant_ref
    )
    return property_ref, block_ref, tenant_ref


class MatchingStrategy(ABC):
    @abstractmethod
    def match(
        self, description: str, db_cursor: Optional[sqlite3.Cursor]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        pass


class IrregularTenantRefStrategy(MatchingStrategy):
    def match(
        self, description: str, db_cursor: Optional[sqlite3.Cursor]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        property_ref, block_ref, tenant_ref = checkForIrregularTenantRefInDatabase(
            description, db_cursor
        )
        if property_ref and block_ref and tenant_ref:
            return property_ref, block_ref, tenant_ref
        return None, None, None


class RegexStrategy(MatchingStrategy):
    def __init__(self, regex: re.Pattern):
        self.regex = regex

    def match(
        self, description: str, db_cursor: Optional[sqlite3.Cursor]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        match = re.search(self.regex, description)
        if match:
            property_ref, block_ref, tenant_ref = (
                getPropertyBlockAndTenantRefsFromRegexMatch(match)
            )
            if db_cursor and not doubleCheckTenantRef(
                db_cursor, tenant_ref, description
            ):
                return None, None, None
            return property_ref, block_ref, tenant_ref
        return None, None, None


class SpecialCaseStrategy(MatchingStrategy):
    def match(
        self, description: str, db_cursor: Optional[sqlite3.Cursor]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        match = re.search(PBT_REGEX_SPECIAL_CASES, description)
        if match:
            property_ref = match.group(1)
            block_ref = "{}-{}".format(match.group(1), match.group(2))
            tenant_ref = "{}-{}-{}".format(
                match.group(1), match.group(2), match.group(3)
            )
            if db_cursor:
                tenant_ref = removeDCReferencePostfix(tenant_ref)
                if not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                    property_ref, block_ref, tenant_ref = correctKnownCommonErrors(
                        property_ref, block_ref, tenant_ref
                    )
                    if not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                        return None, None, None
            elif not (
                (
                    property_ref
                    in ["093", "094", "095", "096", "099", "124", "132", "133", "134"]
                )
                or (
                    property_ref in ["020", "022", "039", "053", "064"]
                    and match.group(3)[-1] != "Z"
                )
            ):
                return None, None, None
            return property_ref, block_ref, tenant_ref
        return None, None, None


class NoHyphenRegexStrategy(MatchingStrategy):
    def match(
        self, description: str, db_cursor: Optional[sqlite3.Cursor]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        match = (
            re.search(PBT_REGEX_NO_HYPHENS, description)
            or re.search(PBT_REGEX_NO_HYPHENS_SPECIAL_CASES, description)
            or re.search(PBT_REGEX_NO_TERMINATING_SPACE, description)
            or re.search(PBT_REGEX_NO_BEGINNING_SPACE, description)
        )
        if match:
            property_ref, block_ref, tenant_ref = (
                getPropertyBlockAndTenantRefsFromRegexMatch(match)
            )
            if db_cursor and not doubleCheckTenantRef(
                db_cursor, tenant_ref, description
            ):
                property_ref, block_ref, tenant_ref = correctKnownCommonErrors(
                    property_ref, block_ref, tenant_ref
                )
                if not doubleCheckTenantRef(db_cursor, tenant_ref, description):
                    return None, None, None
            return property_ref, block_ref, tenant_ref
        return None, None, None


# class PostProcessStrategy(MatchingStrategy):
#     def match(self, description: str, db_cursor: Optional[sqlite3.Cursor]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
#         property_ref, block_ref, tenant_ref = super().match(description, db_cursor)
#         return postProcessPropertyBlockTenantRefs(property_ref, block_ref, tenant_ref)


class PropertyBlockTenantRefMatcher:
    def __init__(self):
        self.strategies: List[MatchingStrategy] = []

    def add_strategy(self, strategy: MatchingStrategy):
        self.strategies.append(strategy)

    def match(
        self, description: str, db_cursor: Optional[sqlite3.Cursor]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        for strategy in self.strategies:
            property_ref, block_ref, tenant_ref = strategy.match(description, db_cursor)
            if property_ref or block_ref or tenant_ref:
                return property_ref, block_ref, tenant_ref
        return None, None, None


def checkForIrregularTenantRefInDatabase(
    reference: str, db_cursor: Optional[sqlite3.Cursor]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # Look for known irregular transaction refs which we know some tenants use
    if db_cursor:
        tenant_ref = get_single_value(
            db_cursor, SELECT_IRREGULAR_TRANSACTION_TENANT_REF_SQL, (reference,)
        )
        if tenant_ref:
            return getPropertyBlockAndTenantRefs(tenant_ref)  # Parse tenant reference
        # else:
        #    transaction_ref_data = get_data(db_cursor, SELECT_ALL_IRREGULAR_TRANSACTION_REFS_SQL)
        #    for tenant_ref, transaction_ref_pattern in transaction_ref_data:
        #        pass
    return None, None, None


def getPropertyBlockAndTenantRefs(
    reference: str, db_cursor: Optional[sqlite3.Cursor] = None
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not isinstance(reference, str):
        return None, None, None

    description = str(reference).strip()

    matcher = PropertyBlockTenantRefMatcher()
    matcher.add_strategy(IrregularTenantRefStrategy())
    matcher.add_strategy(RegexStrategy(PBT_REGEX))
    matcher.add_strategy(RegexStrategy(PBT_REGEX_FWD_SLASHES))
    matcher.add_strategy(RegexStrategy(PBT_REGEX2))
    matcher.add_strategy(RegexStrategy(PBT_REGEX3))
    matcher.add_strategy(RegexStrategy(PBT_REGEX4))
    matcher.add_strategy(SpecialCaseStrategy())
    matcher.add_strategy(NoHyphenRegexStrategy())
    # matcher.add_strategy(PostProcessStrategy())

    property_ref, block_ref, tenant_ref = matcher.match(description, db_cursor)
    return postProcessPropertyBlockTenantRefs(property_ref, block_ref, tenant_ref)
