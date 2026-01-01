from django.utils.translation import gettext as _

from attendance.models import AttendanceLog
from employee.models import ShiftSchedule
from datetime import timedelta

IS_WINDOWS = True
WINDOWS_PG_DUMP_PATH = r'C:\Program Files\PostgreSQL\16\bin\pg_dump.exe'

MIN_YEAR = 1397
MIN_OUT_DELTA = timedelta(minutes=15)  # threshold for minimum time between in/out
MIN_LATE_DELTA = timedelta(hours=2)  # threshold for minimum time between log time and clock in/out window time
AUTO_DOWNLOAD_ATT_LOGS_INTERVAL = 5  # the value is in minutes
CLEAR_ATT_LOGS_IF_MORE_THAN = 200  # the value is describing the number of logs
# this is for UFace800 pro
VERIFICATION_MAP = {
    0: AttendanceLog.VerificationType.MANUAL,
    1: AttendanceLog.VerificationType.FINGERPRINT,
    4: AttendanceLog.VerificationType.CARD,
    3: AttendanceLog.VerificationType.PIN,  # fingerprint + PIN
    15: AttendanceLog.VerificationType.FACE,
    25: AttendanceLog.VerificationType.IRIS,  # could be palm or advanced face
}

# Annual leave limits per type (days per Jalali year)
LEAVE_LIMITS = {
    'PT': 20,  # Pastime
    'SC': 20,  # Sick
    'NS': 105,  # Maternity/Paternity
    'UR': 10,  # Emergency
    'DS': 0,  # Salary Deduction (no limit)
    'DY': 0,  # Duty Assignment
    'HJ': 40,  # Hajj
}

# Afghan/Persian month names, in calendar order
PERSIAN_MONTHS = [
    _('Hamal'),
    _('Sawr'),
    _('Jawza'),
    _('Saratan'),
    _('Asad'),
    _('Sonbola'),
    _('Mizan'),
    _('Aqrab'),
    _('Qaws'),
    _('Jadi'),
    _('Dalwa'),
    _('Hoot'),
]

persian_wdays = {
    0: 'دوشنبه', 1: 'سه شنبه', 2: 'چهار شنبه',
    3: 'پنج شنبه', 4: 'جمعه', 5: 'شنبه', 6: 'یک‌شنبه'
}

# mapping python date.weekday() → ShiftSchedule.DayOfWeek
# python: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
PY_TO_SS_DOW_GREGORIAN = {
    0: ShiftSchedule.DayOfWeek.MONDAY,
    1: ShiftSchedule.DayOfWeek.TUESDAY,
    2: ShiftSchedule.DayOfWeek.WEDNESDAY,
    3: ShiftSchedule.DayOfWeek.THURSDAY,
    4: ShiftSchedule.DayOfWeek.FRIDAY,
    5: ShiftSchedule.DayOfWeek.SATURDAY,
    6: ShiftSchedule.DayOfWeek.SUNDAY,
}

PY_TO_SS_DOW_JALALI = {
    0: ShiftSchedule.DayOfWeek.SATURDAY,  # Sat → 1
    1: ShiftSchedule.DayOfWeek.SUNDAY,    # Sun → 2
    2: ShiftSchedule.DayOfWeek.MONDAY,    # Mon → 3
    3: ShiftSchedule.DayOfWeek.TUESDAY,   # Tue → 4
    4: ShiftSchedule.DayOfWeek.WEDNESDAY, # Wed → 5
    5: ShiftSchedule.DayOfWeek.THURSDAY,  # Thu → 6
    6: ShiftSchedule.DayOfWeek.FRIDAY,    # Fri → 7
}

PROTECTED_ROLE_NAMES = ['Admin', 'Employee', 'Head of Department']
