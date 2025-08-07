import typing

from pandas.tseries.holiday import MO, AbstractHolidayCalendar, EasterMonday, GoodFriday, Holiday, next_monday, next_monday_or_tuesday  # type: ignore[attr-defined]
from pandas.tseries.offsets import CDay, DateOffset


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


# Define a single business day time offset
BUSINESS_DAY = CDay(calendar=EnglandAndWalesHolidayCalendar())
