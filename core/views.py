from datetime import date

import jdatetime
from django.contrib.auth.decorators import user_passes_test, login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render

from config.constants import PERSIAN_MONTHS
from core.utils import dashboard_get_monthly_attendance, dashboard_get_daily_attendance, dashboard_get_attendance_by_department, shifts_missing_schedule_of_months_for_year
from employee.models import Employee, Department
from django.utils.translation import gettext as _


def any_dashboard_perm(user):
    return (
            user.account_type == 'normal' or
            user.has_perm('core.view_hod_dashboard') or
            user.has_perm('core.view_employee_dashboard')
    )

@login_required(login_url='login')
@user_passes_test(any_dashboard_perm, login_url='login')
def dashboard(request):
    jtoday = jdatetime.date.fromgregorian(date=date.today())
    missing_shifts = shifts_missing_schedule_of_months_for_year(jtoday.year)
    return render(request, 'core/dashboard.html', {
        'missing_shifts': missing_shifts,
    })

@login_required(login_url='login')
@user_passes_test(any_dashboard_perm, login_url='login')
def dashboard_data(request):
    user = request.user

    # defaults
    employee_qs = None
    department_qs = None

    # ── Admins (normal) ──────────────────────────────────────────────
    if user.account_type == 'normal':
        # no filter → all employees, all departments
        department_qs = None

    # ── Employees (including HOD) ──────────────────────────────────────
    elif user.account_type == 'employee':
        # HEAD OF DEPARTMENT
        if user.has_perm('core.view_hod_dashboard'):
            me = Employee.objects.get(user=user)
            employee_qs = Employee.objects.filter(
                department=me.department,
                is_archive=False
            )
            department_qs = Department.objects.filter(pk=me.department_id)

        # PLAIN EMPLOYEE
        elif user.has_perm('core.view_employee_dashboard'):
            me = Employee.objects.get(user=user)
            employee_qs = Employee.objects.filter(pk=me.pk)

        else:
            return HttpResponseForbidden()

    else:
        return HttpResponseForbidden()

    # ── Dates ───────────────────────────────────────────────────────────
    # today = date(2025, 4, 22)
    today = date.today()
    jtoday = jdatetime.date.fromgregorian(date=today)
    jy, jm = jtoday.year, jtoday.month
    month_name = PERSIAN_MONTHS[jm - 1]

    # ── Daily (scoped) ──────────────────────────────────────────────────
    daily = dashboard_get_daily_attendance(
        today,
        is_follow_schedule=True,
        employee_qs=employee_qs
    )
    ci, co = daily['clock_in'], daily['clock_out']
    pres_m, abs_m, late_m = ci['present_count'], ci['absent_count'], ci['late_count']
    pres_e, abs_e, late_e = co['present_count'], co['absent_count'], co['late_count']

    total = (employee_qs.count()
             if employee_qs is not None
             else Employee.objects.filter(is_archive=False).count())

    # ── Monthly (scoped via employee_qs) ────────────────────────────────
    monthly = dashboard_get_monthly_attendance(
        jy, jm,
        is_follow_schedule=True,
        employee_qs=employee_qs
    )

    # ── Department bar (admins only) ──────────────────────────────────
    dept_data = None
    if user.account_type == 'normal':
        dept_data = dashboard_get_attendance_by_department(
            today,
            is_follow_schedule=True,
            department_qs=None
        )

    # ── Build payload ───────────────────────────────────────────────────
    resp = {
        'month_name': _(month_name),

        # daily
        'present_morning_count': pres_m,
        'absent_morning_count': abs_m,
        'late_morning_count': late_m,
        'present_evening_count': pres_e,
        'absent_evening_count': abs_e,
        'late_evening_count': late_e,

        'present_morning_pct': round(pres_m / total * 100, 1) if total else 0,
        'absent_morning_pct': round((abs_m + late_m) / total * 100, 1) if total else 0,
        'present_evening_pct': round(pres_e / total * 100, 1) if total else 0,
        'absent_evening_pct': round((abs_e + late_e) / total * 100, 1) if total else 0,

        # monthly
        'monthly': monthly,
    }

    # department chart only for admins
    if dept_data is not None:
        resp['department'] = dept_data

    return JsonResponse(resp)
