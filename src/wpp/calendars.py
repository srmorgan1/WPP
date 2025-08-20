import logging  # Import logging
import os
from functools import lru_cache

import pandas as pd
from pandas.tseries.holiday import MO, AbstractHolidayCalendar, EasterMonday, GoodFriday, Holiday, next_monday, next_monday_or_tuesday  # type: ignore[attr-defined]
from pandas.tseries.offsets import CDay, DateOffset

# Assuming these imports are available from other wpp modules
from .config import get_wpp_static_input_dir
from .utils import getLatestMatchingFileName


@lru_cache(maxsize=1)
def get_holidays_from_excel(logger: logging.Logger | None = None) -> dict[str, list]:
    holidays_file_pattern = os.path.join(get_wpp_static_input_dir(), "Holidays.xlsx")
    holidays_xls_file = getLatestMatchingFileName(holidays_file_pattern)

    if not holidays_xls_file:
        if logger:
            logger.warning("Holidays.xlsx not found. No additional holidays will be loaded.")
        return {"Date": [], "Description": []}

    try:
        holidays_df = pd.read_excel(holidays_xls_file, header=0)

        if "Date" not in holidays_df.columns or "Description" not in holidays_df.columns:
            if logger:
                logger.warning("Holidays.xlsx must contain 'Date' and 'Description' columns. No additional holidays will be loaded.")
            return {"Date": [], "Description": []}

        # Convert 'Date' column to datetime objects, coercing errors
        holidays_df["Date_Parsed"] = pd.to_datetime(holidays_df["Date"], errors="coerce")

        # Log rows where Date conversion failed
        failed_conversions = holidays_df[holidays_df["Date_Parsed"].isna()]
        if not failed_conversions.empty and logger:
            logger.warning("Found unparseable dates in Holidays.xlsx:")
            for index, row in failed_conversions.iterrows():
                logger.warning(f"  Row {index + 2}: Original Date Value: '{row['Date']}'")

        # Filter out rows where Date conversion failed (NaT)
        holidays_df.dropna(subset=["Date_Parsed"], inplace=True)

        return {"Date": holidays_df["Date_Parsed"].dt.date.tolist(), "Description": holidays_df["Description"].fillna("").astype(str).tolist()}
    except Exception as e:
        if logger:
            logger.error(f"Error reading Holidays.xlsx: {e}. No additional holidays will be loaded.")
        return {"Date": [], "Description": []}


# Set up holiday calendar
class EnglandAndWalesHolidayCalendar(AbstractHolidayCalendar):
    rules = [
        Holiday("New Years Day", month=1, day=1, observance=next_monday),
        GoodFriday,
        EasterMonday,
        Holiday("Early May bank holiday", month=5, day=1, offset=DateOffset(weekday=MO(1))),
        Holiday("Spring bank holiday", month=5, day=31, offset=DateOffset(weekday=MO(-1))),
        Holiday("Summer bank holiday", month=8, day=31, offset=DateOffset(weekday=MO(-1))),
        Holiday("Christmas Day", month=12, day=25, observance=next_monday),
        Holiday("Boxing Day", month=12, day=26, observance=next_monday_or_tuesday),
    ]

    def __init__(self, logger: logging.Logger | None = None, *args, **kwargs):  # Accept logger here
        super().__init__(*args, **kwargs)
        excel_holidays_data = get_holidays_from_excel(logger)  # Pass logger

        dates = excel_holidays_data.get("Date", [])
        descriptions = excel_holidays_data.get("Description", [])

        for holiday_date, holiday_description in zip(dates, descriptions):
            if holiday_date:
                name = holiday_description.strip() if holiday_description and holiday_description.strip() != "" else f"Excel Holiday {holiday_date.strftime('%Y-%m-%d')}"
                self.rules.append(Holiday(name, year=holiday_date.year, month=holiday_date.month, day=holiday_date.day))


# Removed @lru_cache because logger is not hashable
def get_business_day_offset(logger: logging.Logger | None = None) -> CDay:  # Accept logger here
    return CDay(calendar=EnglandAndWalesHolidayCalendar(logger=logger))  # Pass logger to calendar


# Removed global BUSINESS_DAY definition
