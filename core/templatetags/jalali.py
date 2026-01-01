import datetime
import jdatetime
from django import template
from django.utils.translation import get_language

register = template.Library()


@register.filter
def to_jalali(dt, fmt="%Y/%m/%d %H:%M"):
    """
    Convert a Python datetime/date to a Jalali‐formatted string.
    Usage in template: {{ some_datetime|to_jalali:"%Y/%m/%d" }}
    """
    if not dt:
        return ""
    try:
        # if it's a date, use fromgregorian(date=...)
        if hasattr(dt, 'date') and hasattr(dt, 'time'):
            jdt = jdatetime.datetime.fromgregorian(datetime=dt)
        else:
            jdt = jdatetime.date.fromgregorian(date=dt)
        return jdt.strftime(fmt)
    except Exception:
        return dt  # fallback to original


@register.simple_tag
def jalali_now():
    now = datetime.datetime.now()
    wd = now.weekday()  # Monday=0…Sunday=6
    jd = jdatetime.datetime.fromgregorian(datetime=now)

    EN = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    FA = ['دوشنبه', 'سه شنبه', 'چهار شنبه', 'پنج شنبه', 'جمعه', 'شنبه', 'یکشنبه']
    lang = (get_language() or '').lower()

    dayname = EN[wd] if lang.startswith('en') else FA[wd]
    date_str = jd.strftime('%Y-%m-%d')  # always ASCII digits

    # return both pieces in a dict
    return {
        'dayname': dayname,
        'date_str': date_str,
    }
