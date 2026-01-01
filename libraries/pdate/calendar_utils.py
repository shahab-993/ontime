from datetime import date
from types import SimpleNamespace

import jdatetime

from libraries.pdate.civil_date import CivilDate
from libraries.pdate.persian_date import PersianDate

_DIGITS = "0123456789"
_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_TABLE = str.maketrans(_DIGITS, _PERSIAN_DIGITS)

def persian_to_jd(year, month, day):
    """
    Determine Julian day from Persian date
    """
    return PersianDate(year, month, day).to_jdn()

def jd_to_persian(jd):
    """
    Calculate Persian date from Julian day
    """
    p = PersianDate(None, None, None, jd)

    return (p.year, p.month, p.day_of_month)


def civil_to_jd(year, month, day):
    """
    Determine Julian day from Civil date
    """
    return CivilDate(year, month, day).to_jdn()

def jd_to_civil(jd):
    """
    Calculate Civil date from Julian day
    """
    c = CivilDate(None, None, None, jd)

    return (c.year, c.month, c.day_of_month)


def get_today_persian_date():
    today = date.today()
    y, m, d = jd_to_persian(civil_to_jd(today.year, today.month, today.day))
    return SimpleNamespace(year=y, month=m, day=d)


def jalali_datetime_str(gregorian_dt):
    # 1) Convert just the date to Jalali
    jdate = jdatetime.date.fromgregorian(date=gregorian_dt.date())
    # 2) Format the time with Python's datetime (which handles %I correctly)
    time_str = gregorian_dt.strftime('%I:%M %p')  # e.g. "10:33 PM"
    # 3) Build the final string
    return f"{jdate.year}/{jdate.month:02d}/{jdate.day:02d} {time_str}"