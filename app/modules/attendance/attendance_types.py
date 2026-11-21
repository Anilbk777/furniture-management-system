"""Shared types for the attendance module: BS dates, 12-hour times and overtime hours.
If you already have a BsDate type, import yours instead of the one below."""

import re
from datetime import time
from decimal import Decimal
from typing import Annotated

import nepali_datetime
from pydantic import AfterValidator, BeforeValidator, Field, PlainSerializer

STATUSES = ("present", "half_day", "absent", "leave")
NO_WORK_STATUSES = (
    "absent",
    "leave",
)  # no check-in, check-out or overtime on these days
MAX_RANGE_DAYS = 366

_BS_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_TIME_RE = re.compile(r"(1[0-2]|0?[1-9]):([0-5][0-9])\s*([AaPp][Mm])")


# ---------- BS date ('YYYY-MM-DD') ----------
def parse_bs_date(value: str) -> str:
    match = _BS_RE.fullmatch(value.strip())
    if not match:
        raise ValueError("BS date must look like 2081-04-15 (YYYY-MM-DD)")
    year, month, day = map(int, match.groups())
    try:
        nepali_datetime.date(
            year, month, day
        )  # checks the real BS calendar (month lengths)
    except ValueError:
        raise ValueError("This is not a valid BS date")
    return (
        f"{year:04d}-{month:02d}-{day:02d}"  # zero-padded, so text order = date order
    )


def bs_days_between(from_date: str, to_date: str) -> int:
    """Number of days from from_date to to_date (0 when they are the same day)."""
    start = nepali_datetime.date(*map(int, from_date.split("-")))
    end = nepali_datetime.date(*map(int, to_date.split("-")))
    return (end - start).days


# ---------- 12-hour time ('09:30 AM') ----------
def parse_time12(value) -> time:
    if isinstance(value, time):  # values read back from the database
        return value
    match = _TIME_RE.fullmatch(value.strip()) if isinstance(value, str) else None
    if not match:
        raise ValueError("Time must be in 12-hour format like 09:30 AM")
    hour, minute, meridiem = int(match[1]), int(match[2]), match[3].upper()
    return time(hour % 12 + (12 if meridiem == "PM" else 0), minute)


def format_time12(value: time) -> str:
    return f"{value.hour % 12 or 12:02d}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"


BsDate = Annotated[str, AfterValidator(parse_bs_date)]
Time12 = Annotated[
    time,
    BeforeValidator(parse_time12),
    PlainSerializer(format_time12, return_type=str, when_used="json"),
]

# Stored as an exact decimal (2.5, 0.25, ...) and sent to clients as a plain JSON number.
# (when_used='json': inside Python the values stay real time / Decimal objects.)
Hours = Annotated[
    Decimal,
    Field(ge=0, le=24, max_digits=4, decimal_places=2),
    PlainSerializer(float, return_type=float, when_used="json"),
]
TotalHours = Annotated[
    Decimal, PlainSerializer(float, return_type=float, when_used="json")
]  # sums can exceed 24
