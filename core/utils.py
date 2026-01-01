# core/utils.py
from collections import defaultdict
from datetime import datetime, timedelta

import jdatetime
from django.db import transaction
from django.db.models import Sum, Q
from django.db.utils import IntegrityError
from django.utils.timezone import make_aware
from django.utils.translation import gettext as _

from attendance.models import AttendanceLog, Employee, Device
from attendance.models import EmployeeVacation
from config.constants import LEAVE_LIMITS, CLEAR_ATT_LOGS_IF_MORE_THAN, VERIFICATION_MAP, MIN_OUT_DELTA, PY_TO_SS_DOW_GREGORIAN, PY_TO_SS_DOW_JALALI, persian_wdays, MIN_LATE_DELTA, PERSIAN_MONTHS
from employee.models import ShiftSchedule, Department, Shift
from vendors.build.manager import DeviceConfig, is_device_online, get_attendance_logs, delete_device_data


def get_employee_leave_summary(employee, year=None):
    """
    Returns a dict with:
      - 'year': Jalali year
      - 'summary': list of dicts per leave type:
          {
            'type_code': 'PT',
            'type_display': 'Pastime Leave',
            'used': Decimal('5.00'),
            'limit': 20,
            'remaining': 15,
            'percentage': 25.0,
          }
    """
    # 1) Determine Jalali year
    if year is None:
        year = jdatetime.date.today().year

    # 2) Build Gregorian date range
    j_start = jdatetime.date(year, 1, 1)
    j_next = jdatetime.date(year + 1, 1, 1)
    g_start = j_start.togregorian()
    g_end = j_next.togregorian()

    # 3) Aggregate approved leave days by type
    qs = (
        EmployeeVacation.objects
        .filter(
            employee=employee,
            status=EmployeeVacation.Status.APPROVED,
            start_date__gte=g_start,
            start_date__lt=g_end
        )
        .values('type')
        .annotate(used=Sum('days_requested'))
    )
    used_map = {item['type']: item['used'] for item in qs}

    EXCLUDED_TYPES = ['CA']
    # 4) Build the summary list
    summary = []
    for code, label in EmployeeVacation.VacationType.choices:
        if code in EXCLUDED_TYPES:
            continue  # Skip this type

        used = used_map.get(code) or 0
        limit = LEAVE_LIMITS.get(code, 0)
        # If limit==0 you could interpret as "no fixed limit"
        remaining = (limit - used) if limit > 0 else None
        percentage = float(used / limit * 100) if limit > 0 else None

        summary.append({
            'type_code': code,
            'type_display': label,
            'used': used,
            'limit': limit,
            'remaining': remaining,
            'percentage': percentage,
        })

    return {
        'year': year,
        'summary': summary,
    }


# ------------------------ dashboard ------------------------
def shifts_missing_schedule_of_months_for_year(year):
    """
    Returns a dict mapping each Shift.name to a list of Persian month names
    for which that shift either:
      1) Has no active schedule at all in that month, or
      2) Has at least one active schedule in that month, but where any of
         in_start_time, in_end_time, out_start_time or out_end_time is None.
    """
    missing = {}

    for shift in Shift.objects.all().order_by('name'):
        bad_months = []
        for m in range(1, 13):
            qs = ShiftSchedule.objects.filter(
                year=year,
                month=m,
                shift=shift,
                is_active=True
            )
            if not qs.exists():
                # rule (1): no active schedule in this month
                bad_months.append(PERSIAN_MONTHS[m-1])
            else:
                # rule (2): at least one active schedule, but check for incomplete times
                incomplete = qs.filter(
                    Q(in_start_time__isnull=True) |
                    Q(in_end_time__isnull=True) |
                    Q(out_start_time__isnull=True) |
                    Q(out_end_time__isnull=True)
                )
                if incomplete.exists():
                    bad_months.append(PERSIAN_MONTHS[m-1])

        if bad_months:
            missing[shift.name] = bad_months

    return missing

def dashboard_get_daily_attendance(att_date, *, is_follow_schedule=True, employee_qs=None):
    """
    Returns:
      {
        'clock_in':  {'present_count': X, 'late_count': L1, 'absent_count': Y},
        'clock_out': {'present_count': A, 'late_count': L2, 'absent_count': B},
      }
    """

    # 1. Build employee queryset
    all_emps = Employee.objects.filter(is_archive=False)
    emp_qs = employee_qs if employee_qs is not None else all_emps
    total_emps = emp_qs.count()

    # 2. Build schedule map for this day (if needed)
    sched_map = {}
    if is_follow_schedule:
        jday = jdatetime.date.fromgregorian(date=att_date)
        py_dow = jday.weekday()
        ss_dow = PY_TO_SS_DOW_JALALI[py_dow]
        qs = ShiftSchedule.objects.filter(
            year=jday.year,
            month=jday.month,
            day_of_week=ss_dow,
            is_active=True
        )
        sched_map = {sch.shift_id: sch for sch in qs}

    # 3. Fetch logs
    logs_by_emp = defaultdict(list)
    emp_ids = list(emp_qs.values_list('id', flat=True))
    logs_today = AttendanceLog.objects.filter(
        timestamp__date=att_date,
        employee_id__in=emp_ids
    ).order_by('employee_id', 'timestamp')
    for lg in logs_today:
        logs_by_emp[lg.employee_id].append(lg)

    # b) Fetch next-day logs for overnight shifts
    if is_follow_schedule:
        next_day = att_date + timedelta(days=1)
        for emp in emp_qs:
            sch = sched_map.get(emp.shift_id)
            if sch and sch.in_start_time and sch.out_start_time and sch.out_end_time:
                if (
                        sch.out_start_time < sch.in_start_time or
                        sch.out_end_time < sch.in_start_time or
                        sch.out_start_time > sch.out_end_time
                ):
                    logs_next = AttendanceLog.objects.filter(
                        timestamp__date=next_day,
                        employee_id=emp.id,
                        timestamp__time__gte=sch.out_start_time,
                        timestamp__time__lte=sch.out_end_time,
                    ).order_by('timestamp')
                    logs_by_emp[emp.id].extend(logs_next)

    # Helper: test schedule window
    def in_schedule_window(log, sch, punch_type):
        t = log.timestamp.time()
        if punch_type == 'in':
            return sch.in_start_time <= t <= sch.in_end_time
        # out-window may span midnight
        if sch.out_start_time <= sch.out_end_time:
            return sch.out_start_time <= t <= sch.out_end_time
        else:
            return (t >= sch.out_start_time) or (t <= sch.out_end_time)

    # 4. Classify per employee for clock-in and clock-out
    ci_present = ci_late = ci_absent = 0
    co_present = co_late = co_absent = 0

    for emp in emp_qs:
        emp_logs = sorted(logs_by_emp.get(emp.id, []), key=lambda L: L.timestamp)
        if not emp_logs:
            ci_absent += 1
            co_absent += 1
            continue

        sch = sched_map.get(emp.shift_id) if is_follow_schedule else None

        logs_today = [lg for lg in emp_logs if lg.timestamp.date() == att_date]
        logs_next_day = [lg for lg in emp_logs if lg.timestamp.date() == (att_date + timedelta(days=1))]

        is_overnight = False
        if sch and sch.in_start_time and sch.out_start_time and sch.out_end_time:
            is_overnight = (
                    sch.out_start_time < sch.in_start_time or
                    sch.out_end_time < sch.in_start_time or
                    sch.out_start_time > sch.out_end_time
            )

        # CLOCK IN
        if not logs_today:
            ci_absent += 1
        else:
            if is_follow_schedule and sch:
                # Find if any entry is in window
                in_found = any(
                    in_schedule_window(lg, sch, 'in') for lg in logs_today
                )
                if in_found:
                    ci_present += 1
                else:
                    ci_late += 1
            else:
                # Not schedule enforced, any punch = present
                ci_present += 1

        # CLOCK OUT
        if is_overnight:
            if not logs_next_day:
                co_absent += 1
            else:
                if is_follow_schedule and sch:
                    out_found = any(
                        in_schedule_window(lg, sch, 'out') for lg in logs_next_day
                    )
                    if out_found:
                        co_present += 1
                    else:
                        co_late += 1
                else:
                    co_present += 1
        else:
            if not logs_today:
                co_absent += 1
            else:
                if is_follow_schedule and sch:
                    out_found = any(
                        in_schedule_window(lg, sch, 'out') for lg in logs_today
                    )
                    if out_found:
                        co_present += 1
                    else:
                        co_late += 1
                else:
                    co_present += 1

    return {
        'clock_in': {
            'present_count': ci_present,
            'late_count': ci_late,
            'absent_count': ci_absent,
        },
        'clock_out': {
            'present_count': co_present,
            'late_count': co_late,
            'absent_count': co_absent,
        },
    }


def dashboard_get_monthly_attendance(year: int, month: int, is_follow_schedule: bool = True, employee_qs=None):
    """
    Returns a dict:
      {
        'labels': ['1','2',...,'N'],
        'present': [p1,p2,...,pN],
        'absent' : [a1,a2,...,aN],
      }
    for the given Jalali (Persian) year/month.
    - is_follow_schedule: if True, require punches within schedule window for present.
    """
    # 1. Build employee list
    base = Employee.objects.filter(is_archive=False)
    emp_qs = employee_qs.filter(is_archive=False) if employee_qs is not None else base
    employees = list(emp_qs.select_related('shift'))
    total_emps = len(employees)
    if total_emps == 0:
        # no employees → trivial answer
        jstart = jdatetime.date(year, month, 1)
        jnext = (jdatetime.date(year + 1, 1, 1)
                 if month == 12 else jdatetime.date(year, month + 1, 1))
        days = (jnext.togregorian() - jstart.togregorian()).days
        labels = [str(d) for d in range(1, days + 1)]
        return {'labels': labels, 'present': [0] * days, 'absent': [0] * days}

    # 2. Compute Gregorian month range
    jstart = jdatetime.date(year, month, 1)
    jnext = (jdatetime.date(year + 1, 1, 1) if month == 12 else jdatetime.date(year, month + 1, 1))
    gstart = jstart.togregorian()
    gend = jnext.togregorian() - timedelta(days=1)
    days = (jnext.togregorian() - gstart).days

    # 3. Preload shift schedules if enforcing windows
    sched_map = {}
    if is_follow_schedule:
        shift_ids = {e.shift_id for e in employees}
        schedules = ShiftSchedule.objects.filter(
            shift_id__in=shift_ids,
            year=year,
            month=month,
            is_active=True
        )
        sched_map = {(s.shift_id, s.day_of_week): s for s in schedules}

    # 4. Bulk-fetch this month’s logs (and next-day for overnight)
    emp_ids = [e.id for e in employees]
    logs = AttendanceLog.objects.filter(
        timestamp__date__gte=gstart,
        timestamp__date__lte=gend + timedelta(days=1),  # +1 for next-day out
        employee_id__in=emp_ids
    ).order_by('employee_id', 'timestamp')
    logs_by_emp_day = defaultdict(list)
    for lg in logs:
        logs_by_emp_day[(lg.employee_id, lg.timestamp.date())].append(lg)

    # 5. Helper: test schedule window (from your detailed logic)
    def in_schedule_window(log, sch, punch_type):
        t = log.timestamp.time()
        if not sch:
            return False
        if punch_type == 'in':
            if sch.in_start_time is None or sch.in_end_time is None:
                return False
            return sch.in_start_time <= t <= sch.in_end_time
        # for out window
        if sch.out_start_time is None or sch.out_end_time is None:
            return False
        if sch.out_start_time <= sch.out_end_time:
            return sch.out_start_time <= t <= sch.out_end_time
        else:
            # overnight: after out_start (same day) or before out_end (next day)
            return (t >= sch.out_start_time) or (t <= sch.out_end_time)

    # 6. Roll up day by day
    labels = [str(d) for d in range(1, days + 1)]
    present_list = []
    absent_list = []

    for offset in range(days):
        curr_date = gstart + timedelta(days=offset)
        present = 0

        # If enforcing schedule, get the Jalali DOW for this day
        if is_follow_schedule:
            jday = jdatetime.date.fromgregorian(date=curr_date)
            dow = PY_TO_SS_DOW_JALALI[jday.weekday()]

        for emp in employees:
            # get logs for this employee on this day (and next, if overnight)
            logs_today = logs_by_emp_day.get((emp.id, curr_date), [])
            logs_next = logs_by_emp_day.get((emp.id, curr_date + timedelta(days=1)), [])
            sch = sched_map.get((emp.shift_id, dow)) if is_follow_schedule else None

            # Determine overnight shift
            is_overnight = False
            if sch and sch.in_start_time and sch.out_start_time and sch.out_end_time:
                is_overnight = (
                        sch.out_start_time < sch.in_start_time or
                        sch.out_end_time < sch.in_start_time or
                        sch.out_start_time > sch.out_end_time
                )

            if not is_follow_schedule or not sch:
                # Not schedule enforced: any clock-in and any clock-out
                in_exists = any(lg.log_type == AttendanceLog.LogType.CLOCK_IN for lg in logs_today)
                out_exists = any(lg.log_type == AttendanceLog.LogType.CLOCK_OUT for lg in logs_today)
                if in_exists and out_exists:
                    present += 1
            else:
                # Schedule enforced: must have in in window, and out in window (overnight handled)
                if is_overnight:
                    ci = next((lg for lg in logs_today if in_schedule_window(lg, sch, 'in')), None)
                    co = next((lg for lg in logs_next if in_schedule_window(lg, sch, 'out')), None)
                    if ci and co:
                        present += 1
                else:
                    ci = next((lg for lg in logs_today if in_schedule_window(lg, sch, 'in')), None)
                    co = next((lg for lg in logs_today if in_schedule_window(lg, sch, 'out')), None)
                    if ci and co:
                        present += 1

        present_list.append(present)
        absent_list.append(total_emps - present)

    return {
        'labels': labels,
        'present': present_list,
        'absent': absent_list,
    }


def dashboard_get_attendance_by_department(att_date, *, is_follow_schedule=True, department_qs=None):
    """
    If department_qs is provided: returns exactly the daily‐attendance dict
      {
        'clock_in':  {'present_count': X, 'late_count': L1, 'absent_count': Y},
        'clock_out': {'present_count': A, 'late_count': L2, 'absent_count': B},
      }
    for employees in those departments.

    If no department_qs: returns per‐department combined‐presence counts:
      {
        'labels':  ['HR','IT','Sales',...],
        'present': [p_HR, p_IT, p_Sales, ...],
        'absent':  [a_HR, a_IT, a_Sales, ...],
      }
    (no “Unassigned” label).
    """

    # 1. If filtering by department, reuse daily summary
    if department_qs is not None:
        if isinstance(department_qs, Department):
            depts = [department_qs]
        else:
            depts = list(department_qs)
        emp_qs = Employee.objects.filter(
            is_archive=False,
            department__in=depts
        )
        return dashboard_get_daily_attendance(
            att_date,
            is_follow_schedule=is_follow_schedule,
            employee_qs=emp_qs
        )

    # 2. Otherwise, per-department breakdown
    depts = list(Department.objects.all())
    emp_qs = Employee.objects.filter(is_archive=False).select_related('shift', 'department')
    employees = list(emp_qs)

    # no employees → zeroes for each dept
    if not employees:
        return {
            'labels': [d.name for d in depts],
            'present': [0] * len(depts),
            'absent': [0] * len(depts),
        }

    # 3. Build schedule map for Jalali day
    sched_map = {}
    if is_follow_schedule:
        jday = jdatetime.date.fromgregorian(date=att_date)
        py_dow = jday.weekday()
        ss_dow = PY_TO_SS_DOW_JALALI[py_dow]
        shift_ids = {e.shift_id for e in employees}
        schedules = ShiftSchedule.objects.filter(
            shift_id__in=shift_ids,
            year=jday.year,
            month=jday.month,
            day_of_week=ss_dow,
            is_active=True
        )
        sched_map = {s.shift_id: s for s in schedules}

    # 4. Fetch and group logs (main date)
    logs_by_emp = defaultdict(list)
    emp_ids = [e.id for e in employees]
    logs_today = AttendanceLog.objects.filter(
        timestamp__date=att_date,
        employee_id__in=emp_ids
    ).order_by('employee_id', 'timestamp')
    for lg in logs_today:
        logs_by_emp[lg.employee_id].append(lg)

    # b) Next day logs for overnight shifts
    if is_follow_schedule:
        next_day = att_date + timedelta(days=1)
        for emp in employees:
            sch = sched_map.get(emp.shift_id)
            if sch and sch.in_start_time and sch.out_start_time and sch.out_end_time:
                if (
                        sch.out_start_time < sch.in_start_time or
                        sch.out_end_time < sch.in_start_time or
                        sch.out_start_time > sch.out_end_time
                ):
                    logs_next = AttendanceLog.objects.filter(
                        timestamp__date=next_day,
                        employee_id=emp.id,
                        timestamp__time__gte=sch.out_start_time,
                        timestamp__time__lte=sch.out_end_time,
                    ).order_by('timestamp')
                    logs_by_emp[emp.id].extend(logs_next)

    # Helper: test schedule window
    def in_schedule_window(log, sch, punch_type):
        t = log.timestamp.time()
        if punch_type == 'in':
            return sch.in_start_time <= t <= sch.in_end_time
        if sch.out_start_time <= sch.out_end_time:
            return sch.out_start_time <= t <= sch.out_end_time
        else:
            # overnight
            return (t >= sch.out_start_time) or (t <= sch.out_end_time)

    # 5. Group employees by department
    dept_groups = defaultdict(list)
    for emp in employees:
        dept_groups[emp.department_id].append(emp)

    labels, present_list, absent_list = [], [], []
    for dept in depts:
        emps = dept_groups.get(dept.id, [])
        present = 0
        for emp in emps:
            emp_logs = sorted(logs_by_emp.get(emp.id, []), key=lambda L: L.timestamp)
            if not emp_logs:
                continue  # absent by default, see below

            sch = sched_map.get(emp.shift_id) if is_follow_schedule else None
            logs_today = [lg for lg in emp_logs if lg.timestamp.date() == att_date]
            logs_next_day = [lg for lg in emp_logs if lg.timestamp.date() == (att_date + timedelta(days=1))]
            is_overnight = False
            if sch and sch.in_start_time and sch.out_start_time and sch.out_end_time:
                is_overnight = (
                        sch.out_start_time < sch.in_start_time or
                        sch.out_end_time < sch.in_start_time or
                        sch.out_start_time > sch.out_end_time
                )

            # Attendance present = at least one valid punch in *and* out window
            in_ok = False
            out_ok = False
            if not is_follow_schedule or not sch:
                # Not schedule enforced: any punch = present
                in_ok = bool(logs_today)
                out_ok = bool(logs_today)
            elif is_overnight:
                in_ok = any(in_schedule_window(lg, sch, 'in') for lg in logs_today)
                out_ok = any(in_schedule_window(lg, sch, 'out') for lg in logs_next_day)
            else:
                in_ok = any(in_schedule_window(lg, sch, 'in') for lg in logs_today)
                out_ok = any(in_schedule_window(lg, sch, 'out') for lg in logs_today)

            if in_ok and out_ok:
                present += 1
            # else: absent by default

        labels.append(dept.name)
        present_list.append(present)
        absent_list.append(len(emps) - present)

    return {
        'labels': labels,
        'present': present_list,
        'absent': absent_list,
    }


# ------------------------ end ------------------------

# ------------------------ reports ------------------------
def get_daily_attendance(att_date, *, is_follow_schedule=True, has_emp_list=True, employee_qs=None):
    """
    Returns:
      {
        'clock_in':  {'present': [...], 'present_count': X, 'absent_count': Y},
        'clock_out': {'present': [...], 'present_count': X, 'absent_count': Y},
      }
    """
    # ── 1) Build employee queryset ────────────────────────────────
    emp_qs = employee_qs
    total_emps = emp_qs.count()

    # ── 2) Build schedule map for this day (if needed) ────────────
    sched_map = {}
    if is_follow_schedule:
        jday = jdatetime.date.fromgregorian(date=att_date)
        py_dow = jday.weekday()
        ss_dow = PY_TO_SS_DOW_JALALI[py_dow]

        qs = ShiftSchedule.objects.filter(
            year=jday.year,
            month=jday.month,
            day_of_week=ss_dow,
            is_active=True
        )
        sched_map = {sch.shift_id: sch for sch in qs}

    # ── 3) Fetch raw logs ─────────────────────────────────────────
    logs_by_emp = defaultdict(list)
    emp_ids = list(emp_qs.values_list('id', flat=True))

    # a) logs on the main date
    logs_today = AttendanceLog.objects.filter(
        timestamp__date=att_date,
        employee_id__in=emp_ids
    ).order_by('employee_id', 'timestamp')

    for lg in logs_today:
        logs_by_emp[lg.employee_id].append(lg)

    # b) for each emp whose schedule is overnight, also fetch next-day logs
    if is_follow_schedule:
        next_day = att_date + timedelta(days=1)
        for emp in emp_qs:
            sch = sched_map.get(emp.shift_id)
            # Detect overnight: out_end_time < in_start_time (means checkout is next day)
            if sch and sch.in_start_time and sch.out_start_time and sch.out_end_time:
                # Detect overnight shift as before...
                if (
                        sch.out_start_time < sch.in_start_time or
                        sch.out_end_time < sch.in_start_time or
                        sch.out_start_time > sch.out_end_time
                ):
                    logs_next = AttendanceLog.objects.filter(
                        timestamp__date=next_day,
                        employee_id=emp.id,
                        timestamp__time__gte=sch.out_start_time,
                        timestamp__time__lte=sch.out_end_time,
                    ).order_by('timestamp')
                    logs_by_emp[emp.id].extend(logs_next)

    # helper to test schedule window
    def in_schedule_window(log, sch, punch_type):
        t = log.timestamp.time()
        if punch_type == 'in':
            return sch.in_start_time <= t <= sch.in_end_time
        # out-window may span midnight
        if sch.out_start_time <= sch.out_end_time:
            return sch.out_start_time <= t <= sch.out_end_time
        else:
            # overnight: after out_start (same day) or before out_end (next day)
            return (t >= sch.out_start_time) or (t <= sch.out_end_time)

    # ── 4) Classify per employee ──────────────────────────────────
    ci_present = []
    co_present = []

    for emp in emp_qs:
        emp_logs = sorted(logs_by_emp.get(emp.id, []), key=lambda L: L.timestamp)
        if not emp_logs:
            continue

        # 4a) classify by count
        ci = None
        co = None
        sch = sched_map.get(emp.shift_id) if is_follow_schedule else None

        logs_today = [lg for lg in emp_logs if lg.timestamp.date() == att_date]
        logs_next_day = [lg for lg in emp_logs if lg.timestamp.date() == (att_date + timedelta(days=1))]

        is_overnight = False
        if sch and sch.in_start_time and sch.out_start_time and sch.out_end_time:
            is_overnight = (
                    sch.out_start_time < sch.in_start_time or
                    sch.out_end_time < sch.in_start_time or
                    sch.out_start_time > sch.out_end_time
            )

        if is_overnight:
            ci = next((lg for lg in logs_today if in_schedule_window(lg, sch, 'in')), None)
            co = next((lg for lg in logs_next_day if in_schedule_window(lg, sch, 'out')), None)
        else:
            # your existing normal shift logic here
            # For example:
            if logs_today:
                ci = next((lg for lg in logs_today if in_schedule_window(lg, sch, 'in')), None)
                co = next((lg for lg in logs_today if in_schedule_window(lg, sch, 'out')), None)
            else:
                ci = None
                co = None

        if ci:
            ci_present.append({
                'employee_id': emp.id,
                'timestamp': ci.timestamp,
                'verification_type': ci.verification_type,
                'device_id': ci.device_id,
            })
        if co:
            co_present.append({
                'employee_id': emp.id,
                'timestamp': co.timestamp,
                'verification_type': co.verification_type,
                'device_id': co.device_id,
            })

    # ── 5) Package results ───────────────────────────────────────
    def make_section(present_list):
        cnt = len(present_list)
        return {
            'present': present_list if has_emp_list else None,
            'present_count': cnt,
            'absent_count': total_emps - cnt
        }

    return {
        'clock_in': make_section(ci_present),
        'clock_out': make_section(co_present),
    }


def get_monthly_attendance(year, month, *, is_follow_schedule=True, employee_qs=None):
    """
    Returns (days, grid):
      days = [ { date, num, weekday, is_holiday }, … ]
      grid = [
        {
          'employee': <Employee>,
          'attendance': [
            {am, pm, am_time, pm_time, late, on_leave, public_holiday}, …
          ],
          'present_count': int,
          'absent_count': int,
          'leave_count': int,
          'consideration': str,
          'present_days': int,
          'leave_days': int,
          'absent_days': int,
        }, …
      ]
    """
    # 1) Gregorian range
    jstart = jdatetime.date(year, month, 1)
    jnext = jdatetime.date(year + (month // 12), (month % 12) + 1, 1)
    gstart = jstart.togregorian()
    gend = jnext.togregorian() - timedelta(days=1)

    # 2) Build days array (exclude Fridays)
    days = []
    cur = gstart
    while cur <= gend:
        if cur.weekday() != 4:
            jd = jdatetime.date.fromgregorian(date=cur)
            days.append({
                'date': cur,
                'num': jd.strftime('%d'),
                'weekday': persian_wdays[cur.weekday()],
                'is_holiday': False,
            })
        cur += timedelta(days=1)

    # 3) Employee queryset & ordering
    emp_qs = employee_qs.order_by('user__first_name')
    emp_ids = list(emp_qs.values_list('id', flat=True))

    # 4) Preload attendance logs (all month and next-day for overnight shifts)
    logs = AttendanceLog.objects.filter(
        timestamp__date__range=(gstart, gend + timedelta(days=1)),  # +1 for overnight
        employee_id__in=emp_ids
    ).order_by('employee_id', 'timestamp')
    emp_day_logs = defaultdict(list)
    for lg in logs:
        emp_day_logs[(lg.employee_id, lg.timestamp.date())].append(lg)

    # 5) Preload schedules
    sched_map = {}
    if is_follow_schedule:
        for sch in ShiftSchedule.objects.filter(year=year, month=month, is_active=True):
            sched_map[(sch.shift_id, sch.day_of_week)] = sch

    # 6) Preload vacations and reasons
    vac_qs = EmployeeVacation.objects.filter(
        status=EmployeeVacation.Status.APPROVED,
        start_date__lte=gend,
        end_date__gte=gstart
    )
    vac_map = defaultdict(lambda: defaultdict(list))
    considerations_map = defaultdict(lambda: defaultdict(list))
    holiday_reasons = defaultdict(list)
    for vac in vac_qs:
        start = max(vac.start_date, gstart)
        end = min(vac.end_date, gend)
        curd = start
        while curd <= end:
            if vac.type == EmployeeVacation.VacationType.GENERAL_HOLIDAY:
                reason = vac.reason or _('Public Holiday')
                holiday_reasons[curd].append(reason)
            elif vac.type == EmployeeVacation.VacationType.CONSIDERATIONS:
                # Just show in consideration, do NOT mark as leave or affect attendance
                if vac.reason:
                    considerations_map[vac.employee_id][curd].append(vac.reason)
            else:
                if vac.reason:
                    vac_map[vac.employee_id][curd].append(vac.reason)
            curd += timedelta(days=1)
    # mark days with holiday
    for day in days:
        if day['date'] in holiday_reasons:
            day['is_holiday'] = True

    # 7) Weekday-to-DayOfWeek map (to match your schedule day codes)

    # --- Helper for in-schedule logic (from daily logic) ---
    def in_schedule_window(log, sch, punch_type):
        t = log.timestamp.time()
        if punch_type == 'in':
            return sch.in_start_time <= t <= sch.in_end_time
        # out-window may span midnight
        if sch.out_start_time <= sch.out_end_time:
            return sch.out_start_time <= t <= sch.out_end_time
        else:
            # overnight: after out_start (same day) or before out_end (next day)
            return (t >= sch.out_start_time) or (t <= sch.out_end_time)

    # --- Main Grid ---
    grid = []
    total_days = (gend - gstart).days + 1
    num_fridays = 0
    cur = gstart
    while cur <= gend:
        if cur.weekday() == 4:
            num_fridays += 1
        cur += timedelta(days=1)

    for emp in emp_qs:
        row = {
            'employee': emp,
            'attendance': [],
            'present_count': 0,
            'absent_count': 0,
            'leave_count': 0,
            'consideration': ''
        }
        cons = []
        shift_id = emp.shift_id

        for d in days:
            cell = {
                'am': False, 'am_time': '',
                'pm': False, 'pm_time': '',
                'late': '', 'on_leave': False,
                'public_holiday': False
            }
            date = d['date']
            dow = PY_TO_SS_DOW_GREGORIAN[date.weekday()]
            sch = sched_map.get((shift_id, dow)) if is_follow_schedule else None
            # skip unscheduled
            if is_follow_schedule and not sch:
                row['attendance'].append(cell)
                continue
            # public holiday
            if date in holiday_reasons:
                cell['public_holiday'] = True
                row['leave_count'] += 1
                cons.extend(holiday_reasons[date])
                row['attendance'].append(cell)
                continue
            # employee leave
            reasons = vac_map[emp.id].get(date, [])
            # Add consideration notes (these do not affect attendance)
            c_notes = considerations_map[emp.id].get(date, [])
            if c_notes:
                cons.extend(c_notes)
            if reasons:
                cell['on_leave'] = True
                row['leave_count'] += 1
                cons.extend(reasons)
                row['attendance'].append(cell)
                continue

            # --- LOGIC FROM get_daily_attendance for clock-in/out ---
            # Get logs for this employee on this date (and next day for overnight)
            emp_logs = sorted(emp_day_logs.get((emp.id, date), []), key=lambda L: L.timestamp)
            next_day_logs = sorted(emp_day_logs.get((emp.id, date + timedelta(days=1)), []), key=lambda L: L.timestamp)
            is_overnight = False
            if sch and sch.in_start_time and sch.out_start_time and sch.out_end_time:
                is_overnight = (
                        sch.out_start_time < sch.in_start_time or
                        sch.out_end_time < sch.in_start_time or
                        sch.out_start_time > sch.out_end_time
                )

            ci, co = None, None
            if is_overnight:
                if emp_logs:
                    ci = next((lg for lg in emp_logs if in_schedule_window(lg, sch, 'in')), None)
                if next_day_logs:
                    co = next((lg for lg in next_day_logs if in_schedule_window(lg, sch, 'out')), None)
            else:
                if emp_logs:
                    ci = next((lg for lg in emp_logs if in_schedule_window(lg, sch, 'in')), None)
                    co = next((lg for lg in emp_logs if in_schedule_window(lg, sch, 'out')), None)

            if ci:
                cell['am'] = True
                cell['am_time'] = ci.timestamp.strftime('%I:%M:%S %p')
                row['present_count'] += 1
            if co:
                cell['pm'] = True
                cell['pm_time'] = co.timestamp.strftime('%I:%M:%S %p')
                row['present_count'] += 1

            # Optional: late/extra log logic (not strictly needed)
            late_threshold = MIN_LATE_DELTA  # Define the threshold for considering a log as absent
            if not ci and emp_logs and sch:
                late_in = min(emp_logs, key=lambda x: x.timestamp)
                log_time = late_in.timestamp.time()
                # Convert schedule in_start_time to a comparable datetime for the same day
                sched_in_time = datetime.combine(date, sch.in_start_time)
                log_datetime = datetime.combine(date, log_time)
                # Check if the log is within 2 hours of the in_start_time
                time_diff = abs((log_datetime - sched_in_time).total_seconds())
                if time_diff <= late_threshold.total_seconds():
                    cell['late'] = late_in.timestamp.strftime('%I:%M:%S %p')
                else:
                    row['absent_count'] += 1

            if not co and emp_logs and sch:
                late_out = max(emp_logs, key=lambda x: x.timestamp)
                log_time = late_out.timestamp.time()
                # Convert schedule out_start_time to a comparable datetime
                sched_out_time = datetime.combine(date, sch.out_start_time)
                log_datetime = datetime.combine(date, log_time)
                # Handle overnight schedules
                if sch.out_start_time > sch.out_end_time and log_time <= sch.out_end_time:
                    # Log is likely on the next day
                    sched_out_time = datetime.combine(date + timedelta(days=1), sch.out_start_time)
                time_diff = abs((log_datetime - sched_out_time).total_seconds())
                if time_diff <= late_threshold.total_seconds():
                    cell['late'] = late_out.timestamp.strftime('%I:%M:%S %p')
                else:
                    row['absent_count'] += 1

            if not emp_logs and not next_day_logs:
                row['absent_count'] += 1

            row['attendance'].append(cell)

        # dedupe considerations
        unique_cons = []
        for r in cons:
            if r not in unique_cons:
                unique_cons.append(r)
        row['consideration'] = ', '.join(unique_cons)

        # SUMMARY COUNTS (with rules)
        total_days = len(days)
        # present_days: both am & pm on time and no late/leave/holiday
        present_days = sum(
            1 for cell in row['attendance']
            if cell['am'] and cell['pm'] and not cell['late'] and not cell['on_leave'] and not cell['public_holiday']
        )
        leave_days = sum(
            1 for cell in row['attendance']
            if cell['on_leave'] or cell['public_holiday']
        ) + num_fridays

        # Only non-Fridays are possible for absent (attendance grid days)
        absent_days = len(row['attendance']) - present_days - (leave_days - num_fridays)

        row['present_days'] = present_days
        row['leave_days'] = leave_days
        row['absent_days'] = absent_days

        grid.append(row)

    return days, grid


def group_logs_by_min_interval(logs, min_interval_minutes=15):
    if not logs:
        return []
    grouped = [logs[0]]
    for log in logs[1:]:
        if (log.timestamp - grouped[-1].timestamp) >= min_interval_minutes:
            grouped.append(log)
    return grouped


def get_attendance_summary(year, month, *, is_follow_schedule=True, employee_qs=None):
    """
    Summarize each employee's attendance and leave totals for a given Jalali month:
    Returns a list of dicts with keys:
      - employee
      - haj, pastime, n_sick, sick, urgency, deficit_salary, duty, general_holiday
      - fri_days, present, leave, absent
      - absent_list: list of Jalali day numbers as strings
      - consideration: comma-joined vacation reasons
    """
    # 1) Determine date range
    jstart = jdatetime.date(year, month, 1)
    jnext = jdatetime.date(year + (month // 12), (month % 12) + 1, 1)
    gstart = jstart.togregorian()
    gend = jnext.togregorian() - timedelta(days=1)

    # 2) Build working days (exclude Fridays for attendance grid)
    days = []
    cur = gstart
    while cur <= gend:
        if cur.weekday() != 4:
            days.append(cur)
        cur += timedelta(days=1)

    # 3) Count Fridays in month
    total_days = (gend - gstart).days + 1
    fri_days = sum(1 for i in range(total_days)
                   if (gstart + timedelta(days=i)).weekday() == 4)

    # 4) Employee queryset
    emps = employee_qs

    # 5) Fetch logs (for full month + 1 day for overnight support)
    emp_ids = list(emps.values_list('id', flat=True))
    logs = AttendanceLog.objects.filter(
        timestamp__date__range=(gstart, gend + timedelta(days=1)),
        employee_id__in=emp_ids
    )
    day_logs = defaultdict(list)
    for lg in logs:
        day_logs[(lg.employee_id, lg.timestamp.date())].append(lg)

    # 6) Fetch schedules if needed
    sched = {}
    if is_follow_schedule:
        for s in ShiftSchedule.objects.filter(year=year, month=month, is_active=True):
            sched[(s.shift_id, s.day_of_week)] = s

    # 7) Fetch vacations
    vacs = EmployeeVacation.objects.filter(
        status=EmployeeVacation.Status.APPROVED,
        start_date__lte=gend, end_date__gte=gstart
    )
    type_counts = defaultdict(lambda: defaultdict(int))
    holiday_days = set()
    holiday_reasons = defaultdict(list)
    considerations_map = defaultdict(lambda: defaultdict(list))
    emp_vacation_days = defaultdict(set)
    for vac in vacs:
        vs = max(vac.start_date, gstart)
        ve = min(vac.end_date, gend)
        d = vs
        while d <= ve:
            if d.weekday() == 4:
                d += timedelta(days=1)
                continue
            if vac.type == EmployeeVacation.VacationType.GENERAL_HOLIDAY:
                holiday_days.add(d)
                if vac.reason:
                    holiday_reasons[d].append(vac.reason)
            elif vac.type == EmployeeVacation.VacationType.CONSIDERATIONS:
                if vac.reason:
                    considerations_map[vac.employee_id][d].append(vac.reason)
            else:
                type_counts[vac.employee_id][vac.type] += 1
                emp_vacation_days[vac.employee_id].add(d)
            d += timedelta(days=1)

    # 8) Helper for schedule window logic
    def in_schedule_window(log, sch, punch_type):
        t = log.timestamp.time()
        if punch_type == 'in':
            return sch.in_start_time <= t <= sch.in_end_time
        # out-window may span midnight
        if sch.out_start_time <= sch.out_end_time:
            return sch.out_start_time <= t <= sch.out_end_time
        else:
            # overnight: after out_start (same day) or before out_end (next day)
            return (t >= sch.out_start_time) or (t <= sch.out_end_time)

    # 9) Summary build
    summary = []
    for emp in emps.order_by('user__first_name'):
        row = {'employee': emp}
        # leave type fields
        row['haj'] = type_counts[emp.id].get('HJ', 0)
        row['pastime'] = type_counts[emp.id].get('PT', 0)
        row['n_sick'] = type_counts[emp.id].get('NS', 0)
        row['sick'] = type_counts[emp.id].get('SC', 0)
        row['urgency'] = type_counts[emp.id].get('UR', 0)
        row['deficit_salary'] = type_counts[emp.id].get('DS', 0)
        row['duty'] = type_counts[emp.id].get('DY', 0)
        row['general_holiday'] = len(holiday_days)
        row['fri_days'] = fri_days

        present = 0
        absent_list = []
        consider = []

        for d in days:
            jd_day = jdatetime.date.fromgregorian(date=d).strftime('%d')
            # Holiday?
            if d in holiday_days:
                consider.extend(holiday_reasons.get(d, []))
                continue
            # Employee vacation?
            if d in emp_vacation_days[emp.id]:
                consider.extend([vac.reason for vac in vacs if vac.employee_id == emp.id and max(vac.start_date, gstart) <= d <= min(vac.end_date, gend) and vac.reason])
                continue

            # Add any consideration notes (do not skip the day)
            c_notes = considerations_map[emp.id].get(d, [])
            if c_notes:
                consider.extend(c_notes)

            # Schedule for this day
            if is_follow_schedule:
                dow = PY_TO_SS_DOW_GREGORIAN[d.weekday()]
                sch = sched.get((emp.shift_id, dow))
                if not sch:
                    continue  # Skip unscheduled days
            else:
                sch = None

            # --- Use 100% monthly logic here ---
            emp_logs = sorted(day_logs.get((emp.id, d), []), key=lambda x: x.timestamp)
            next_day_logs = sorted(day_logs.get((emp.id, d + timedelta(days=1)), []), key=lambda x: x.timestamp)

            is_overnight = False
            if sch and sch.in_start_time and sch.out_start_time and sch.out_end_time:
                is_overnight = (
                        sch.out_start_time < sch.in_start_time or
                        sch.out_end_time < sch.in_start_time or
                        sch.out_start_time > sch.out_end_time
                )

            ci, co = None, None
            if is_overnight:
                if emp_logs:
                    ci = next((lg for lg in emp_logs if in_schedule_window(lg, sch, 'in')), None)
                if next_day_logs:
                    co = next((lg for lg in next_day_logs if in_schedule_window(lg, sch, 'out')), None)
            else:
                if emp_logs:
                    ci = next((lg for lg in emp_logs if in_schedule_window(lg, sch, 'in')), None)
                    co = next((lg for lg in emp_logs if in_schedule_window(lg, sch, 'out')), None)


            if ci and co:
                present += 1
            else:
                absent_list.append({'day': jd_day, 'is_thursday': d.weekday() == 3})

        row['present'] = present
        leave_days = (row['haj'] + row['pastime'] + row['n_sick'] + row['sick'] +
                      row['urgency'] + row['deficit_salary'] + row['duty'] +
                      row['general_holiday'] + row['fri_days'])
        row['leave'] = leave_days
        row['absent'] = total_days - present - leave_days
        row['absent_list'] = absent_list
        row['consideration'] = ', '.join(dict.fromkeys(consider))

        summary.append(row)

    return summary


def chunked(sequence, size):
    return [sequence[i: i + size] for i in range(0, len(sequence), size)]

def sync_attendance_logs_raw():
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{now}  🔄 Syncing RAW attendance logs from devices…")

    devices = Device.objects.filter(
        status=Device.Status.ENABLED,
        device_type=Device.DeviceType.ATTENDANCE
    )

    total_fetched = 0
    total_saved = 0

    for device in devices:
        cfg = DeviceConfig(
            ip=device.ip_address,
            port=device.port,
            com_key=device.com_key
        )

        if not is_device_online(cfg):
            print(f"❌ Device {device.name} offline—skipping.")
            continue

        try:
            logs = get_attendance_logs(cfg)
        except Exception as e:
            print(f"❌ Failed to fetch from {device.name}: {e}")
            continue

        total_fetched += len(logs)
        if not logs:
            print(f"ℹ️ No new logs on {device.name}.")
            continue

        entries = []
        for raw in logs:
            uid = raw.get('user_id')
            ts = raw.get('timestamp')
            try:
                emp = Employee.objects.get(employee_id=uid)
            except Employee.DoesNotExist:
                continue

            # make sure timestamp is timezone-aware
            if ts.tzinfo is None:
                ts = make_aware(ts)

            raw_status = raw.get('status', 1)
            try:
                raw_status = int(raw_status)
            except (TypeError, ValueError):
                raw_status = 1  # default to fingerprint if it’s really busted

            entries.append(AttendanceLog(
                employee=emp,
                device=device,
                timestamp=ts,
                status=raw.get('punch'),
                verification_type=VERIFICATION_MAP.get(
                    raw.get('status'),
                    AttendanceLog.VerificationType.MANUAL
                ),
                # leave log_type alone (it will be NULL in the DB)
            ))

        # bulk save all raw punches
        try:
            with transaction.atomic():
                AttendanceLog.objects.bulk_create(entries, ignore_conflicts=True)
                total_saved += len(entries)
        except IntegrityError as e:
            print(f"❌ Error saving logs for {device.name}: {e}")

        # optional: clear devices if it has lots of logs
        if len(logs) > CLEAR_ATT_LOGS_IF_MORE_THAN:
            try:
                delete_device_data(cfg, clear_logs=True)
                print(f"🧹 Cleared logs on {device.name}")
            except Exception as e:
                print(f"⚠️ Couldn't clear {device.name}: {e}")

    print("✅ Raw sync complete.")
    print(f"  → Logs fetched: {total_fetched}")
    print(f"  → Records saved: {total_saved}")
