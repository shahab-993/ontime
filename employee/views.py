import json
from datetime import date, datetime

import jdatetime
from django.contrib import messages
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db import transaction, connection
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.templatetags.static import static
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from attendance.models import BiometricRecord
from config.constants import PERSIAN_MONTHS
from core.utils import get_employee_leave_summary
from employee.models import Department, Shift, Employee, ShiftSchedule, EmployeeDocument
from libraries.pdate.calendar_utils import get_today_persian_date, jalali_datetime_str
from users.models import User

@login_required(login_url='login')
@permission_required('core.view_employee_list', raise_exception=True)
def employees(request):
    return render(request, "employees/employees.html")

@login_required(login_url='login')
@permission_required('core.view_employee_list', raise_exception=True)
def fetch_employees(request):
    if request.method != 'POST':
        return JsonResponse({'error': _("Invalid request method.")}, status=400)

    page = int(request.POST.get('page', 1))
    page_size = int(request.POST.get('page_size', 10))
    search_val = request.POST.get('search_value', '').strip()
    order_by = request.POST.get('order_by', 'employee_id')
    order_dir = request.POST.get('order_dir', 'asc')

    # ─── pull in optional dept filter ───────────────────────────
    dept_id = request.POST.get('department')
    # only active employees here
    qs = Employee.objects.select_related('user').filter(is_archive=False)
    # apply department filter if provided
    if dept_id:
        qs = qs.filter(department_id=dept_id)

    total_records = qs.count()

    if search_val:
        qs = qs.filter(
            Q(employee_id__icontains=search_val) |
            Q(user__first_name__icontains=search_val) |
            Q(user__last_name__icontains=search_val) |
            Q(father_name__icontains=search_val) |
            Q(position__icontains=search_val) |
            Q(department__name__icontains=search_val) |
            Q(shift__name__icontains=search_val) |
            Q(user__phone_number__icontains=search_val)

        )
    total_filtered = qs.count()

    # ordering map
    ORDER_MAP = {
        'employee_id': 'employee_id',
        'full_name': 'user__first_name',
        'father_name': 'father_name',
        'position': 'position',
    }
    orm_field = ORDER_MAP.get(order_by, 'user__first_name')
    prefix = '-' if order_dir == 'desc' else ''
    qs = qs.order_by(f'{prefix}{orm_field}')

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    data = []
    default_photo = static('assets/images/user/default_profile_m.jpg')
    for emp in page_obj:
        user = emp.user
        full_name = f"{user.first_name} {user.last_name}".title()
        father_name = emp.father_name.title() if emp.father_name else ''
        position = emp.position.title() if emp.position else ''

        data.append({
            'id': emp.id,
            'employee_id': emp.employee_id,
            'full_name': full_name,
            'father_name': father_name,
            'position': position,
            'department': emp.department.name if emp.department else '',
            'shift': emp.shift.name if emp.shift else '',
            'phone_number': user.phone_number,
            'status': user.is_active,
            'photo': user.profile_photo.url if user.profile_photo else default_photo,
        })

    return JsonResponse({
        'recordsTotal': total_records,
        'recordsFiltered': total_filtered,
        'data': data,
    })

@login_required(login_url='login')
@permission_required('core.view_employee_archive_list', raise_exception=True)
def emp_archive(request):
    return render(request, "employees/emp_archive.html")

@login_required(login_url='login')
@permission_required('core.view_employee_archive_list', raise_exception=True)
def fetch_emp_archive(request):
    if request.method != 'POST':
        return JsonResponse({'error': _("Invalid request method.")}, status=400)

    page = int(request.POST.get('page', 1))
    page_size = int(request.POST.get('page_size', 10))
    search_val = request.POST.get('search_value', '').strip()
    order_by = request.POST.get('order_by', 'employee_id')
    order_dir = request.POST.get('order_dir', 'asc')

    qs = Employee.objects.select_related('user').filter(is_archive=True)
    # ─── pull in optional dept filter ───────────────────────────
    dept_id = request.POST.get('department')
    # only active employees here
    qs = Employee.objects.select_related('user').filter(is_archive=True)
    # apply department filter if provided
    if dept_id:
        qs = qs.filter(department_id=dept_id)


    total_records = qs.count()

    if search_val:
        qs = qs.filter(
            Q(employee_id__icontains=search_val) |
            Q(user__first_name__icontains=search_val) |
            Q(user__last_name__icontains=search_val) |
            Q(father_name__icontains=search_val) |
            Q(position__icontains=search_val) |
            Q(department__name__icontains=search_val) |
            Q(shift__name__icontains=search_val) |
            Q(user__phone_number__icontains=search_val)

        )
    total_filtered = qs.count()

    # ordering map
    ORDER_MAP = {
        'employee_id': 'employee_id',
        'full_name': 'user__first_name',
        'father_name': 'father_name',
        'position': 'position',
    }
    orm_field = ORDER_MAP.get(order_by, 'user__first_name')
    prefix = '-' if order_dir == 'desc' else ''
    qs = qs.order_by(f'{prefix}{orm_field}')

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    data = []
    default_photo = static('assets/images/user/default_profile_m.jpg')
    for emp in page_obj:
        user = emp.user
        full_name = f"{user.first_name} {user.last_name}".title()
        father_name = emp.father_name.title() if emp.father_name else ''
        position = emp.position.title() if emp.position else ''

        data.append({
            'id': emp.id,
            'employee_id': emp.employee_id,
            'full_name': full_name,
            'father_name': father_name,
            'position': position,
            'department': emp.department.name if emp.department else '',
            'shift': emp.shift.name if emp.shift else '',
            'phone_number': user.phone_number,
            'status': user.is_active,
            'photo': user.profile_photo.url if user.profile_photo else default_photo,
        })

    return JsonResponse({
        'recordsTotal': total_records,
        'recordsFiltered': total_filtered,
        'data': data,
    })


@login_required(login_url='login')
@permission_required('core.change_employee', raise_exception=True)
def ajax_toggle_archive(request, employee_id):
    if request.method != 'POST' or request.content_type != 'application/json':
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

    try:
        payload = json.loads(request.body)
        action = payload.get('action')
        reason = payload.get('reason', '').strip()
        archive_date_str = payload.get('archive_date', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Malformed JSON.'}, status=400)

    emp = get_object_or_404(Employee, pk=employee_id)

    if action == 'archive':
        if not reason:
            return JsonResponse({
                'success': False,
                'error': 'Please provide a reason for archiving.'
            }, status=400)

        # Parse archive_date (optional fallback to today)
        if archive_date_str:
            try:
                jdate_parts = [int(part) for part in archive_date_str.split('/')]
                if len(jdate_parts) == 3:
                    jdate = jdatetime.date(*jdate_parts)
                    archive_date = jdate.togregorian()
                else:
                    raise ValueError("Invalid Jalali date format.")
            except Exception:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid archive date format.'
                }, status=400)
        else:
            archive_date = datetime.today().date()

        emp.is_archive = True
        emp.is_active = True
        emp.archive_date = archive_date
        emp.archive_reason = reason

    elif action == 'unarchive':
        emp.is_archive = False
        emp.is_active = False
        emp.archive_date = None
        emp.archive_reason = ''

    else:
        return JsonResponse({'success': False, 'error': 'Unknown action.'}, status=400)

    emp.save()
    return JsonResponse({'success': True, 'is_archive': emp.is_archive})

@login_required(login_url='login')
@permission_required('core.change_employee', raise_exception=True)
@csrf_exempt
def update_employee_status(request):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        emp_id = request.POST.get('id')
        status = request.POST.get('status') == 'true'
        try:
            emp = Employee.objects.select_related('user').get(id=emp_id)
            # toggle the underlying User instead of the Employee archive flag
            emp.user.is_active = status
            emp.user.save()
            return JsonResponse({
                'success': True,
                'status': emp.user.is_active
            })
        except Employee.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': _("Employee not found")
            }, status=404)

    return JsonResponse({
        'success': False,
        'error': _("Invalid request")
    }, status=400)


@login_required(login_url='login')
@permission_required('core.view_employee_profile', raise_exception=True)
def employee_profile(request, employee_id=None):
    """
    - Admins (who have the `core.view_employee_profile` perm) may pass an `employee_id`
      and view anyone’s profile.
    - Employees and HODs ignore the URL arg and only ever see their own.
    """
    user = request.user

    # If the user is in the Employee or Head-of-Department group,
    # force them to their own profile:
    if user.groups.filter(name__in=["Employee", "Head of Department"]).exists():
        # ensure they actually have an employee_profile
        try:
            employee = user.employee_profile
        except Employee.DoesNotExist:
            return redirect("dashboard")  # or 404, or show a message
    else:
        # everyone else must have the view permission
        # (you could also wrap this branch in @permission_required)
        if not user.has_perm("core.view_employee_profile"):
            return redirect("dashboard")
        # and we require an id
        employee = get_object_or_404(Employee, id=employee_id)

    # build the rest of your context exactly as you had it:
    profile_photo_url = (
        employee.user.profile_photo.url
        if getattr(employee.user, "profile_photo", None)
        else static("assets/images/user/default_profile_m.jpg")
    )
    # Mock leave data (replace with actual leave data logic as needed)
    leave_info = get_employee_leave_summary(employee)
    current_year = leave_info['year']
    leave_data = leave_info['summary']

    # ─── Biometric flags ────────────────────────────────────
    bqs = employee.biometric_records.all()
    rfid_active = bqs.filter(biometric_type=BiometricRecord.BiometricType.RFID).exists()
    face_active = bqs.filter(biometric_type=BiometricRecord.BiometricType.FACE).exists()
    # Collect the fingerprint positions (0–9) that exist
    fps = set(bqs
              .filter(biometric_type=BiometricRecord.BiometricType.FINGERPRINT)
              .values_list('finger_position', flat=True))
    # Build individual flags fp_0 … fp_9
    fp_flags = {f'fp_{i}': (i in fps) for i in range(10)}

    context = {
        'employee': employee,
        'leave_data': leave_data,
        'current_year': current_year,
        'profile_photo_url': profile_photo_url,
        'rfid_active': rfid_active,
        'face_active': face_active,
        **fp_flags,
    }

    return render(request, 'employees/employee_profile.html', context)

@login_required(login_url='login')
@permission_required('core.change_employee_password', raise_exception=True)
@require_POST
def ajax_change_employee_password(request, employee_id):
    employee = get_object_or_404(Employee, pk=employee_id)
    user = employee.user

    old = request.POST.get('old_password', '')
    new = request.POST.get('password', '')
    confirm = request.POST.get('confirm_password', '')

    # 1) check old password first
    if not user.check_password(old):
        return JsonResponse({
            'success': False,
            'error': _("Current password is incorrect.")
        }, status=400)

    # 2) then check new/confirm and length
    errors = []
    if new != confirm:
        errors.append(_("New passwords don’t match."))
    if len(new) < 8:
        errors.append(_("New password must be at least 8 characters."))

    if errors:
        return JsonResponse({'success': False, 'errors': errors}, status=400)

    # 3) all good → update
    user.set_password(new)
    user.save()
    return JsonResponse({'success': True})

@login_required(login_url='login')
@permission_required('core.add_employee_documents', raise_exception=True)
@require_POST
def ajax_upload_employee_document(request, employee_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request.'}, status=400)

    employee = get_object_or_404(Employee, pk=employee_id)
    uploaded = request.FILES.get('file')
    description = request.POST.get('description', '').strip()

    if not uploaded:
        return JsonResponse({'error': 'Please choose a file.'}, status=400)

    doc = EmployeeDocument.objects.create(
        employee=employee,
        file=uploaded,
        description=description
    )

    return JsonResponse({
        'success': True,
        'doc': {
            'id': doc.id,
            'name': doc.file.name.rsplit('/', 1)[-1],
            'url': doc.file.url,
            'description': doc.description,
            'uploaded_at': doc.uploaded_at.strftime('%Y-%m-%d %H:%M'),
        }
    })

@login_required(login_url='login')
@permission_required('core.delete_employee_documents', raise_exception=True)
@require_POST
def ajax_delete_employee_document(request, doc_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request.'}, status=400)

    doc = get_object_or_404(EmployeeDocument, pk=doc_id)
    # delete the file from storage first
    if doc.file:
        doc.file.delete(save=False)
    # now delete the database record
    doc.delete()
    return JsonResponse({'success': True})

@login_required(login_url='login')
@permission_required('core.add_employee', raise_exception=True)
def add_employee(request):
    departments = Department.objects.all()
    shifts = Shift.objects.filter(is_active=True)
    work_types = Employee.WORK_TYPE_CHOICES
    roles = Group.objects.all()

    # ─── compute next default employee_id ───
    last = Employee.objects.order_by('-employee_id').first()
    default_employee_id = 100
    if last and last.employee_id is not None:
        try:
            # try to coerce whatever type it is into an int
            last_num = int(last.employee_id)
            default_employee_id = last_num + 1
        except (ValueError, TypeError):
            # not a clean integer, just stick with 100
            pass

    old = {}  # will hold POST data on error

    if request.method == 'POST':
        # — pull everything out —
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        phone_number = request.POST.get('phone_number', '').strip()
        gender = request.POST.get('gender', '')
        profile_photo = request.FILES.get('profile_photo')
        selected_roles = request.POST.getlist('roles')

        employee_id = request.POST.get('employee_id', '').strip()
        father_name = request.POST.get('father_name', '').strip()
        grand_father_name = request.POST.get('grand_father_name', '').strip()
        position = request.POST.get('position', '').strip()
        is_device_admin = bool(request.POST.get('is_device_admin'))
        bast = request.POST.get('bast', '').strip()
        qua_dam = request.POST.get('qua_dam', '').strip()
        legacy_code = request.POST.get('legacy_code', '').strip()
        dept_id = request.POST.get('department')
        shift_id = request.POST.get('shift')
        work_type = request.POST.get('work_type', Employee.FULL_TIME)
        salary_val = request.POST.get('salary') or None
        duty_days = request.POST.get('duty_days') or 0
        extra_info = request.POST.get('extra_info', '').strip()
        is_head_of_dep = bool(request.POST.get('is_head_of_dep'))
        address = request.POST.get('address', '').strip()
        contract_date = request.POST.get('contract_date', '').strip()
        education_degree = request.POST.get('education_degree', '').strip()
        national_id = request.POST.get('national_id', '').strip()

        # keep for re-render on error
        old = request.POST.copy()

        # — validation —
        errors = []
        if password != confirm_password:
            errors.append(_("Passwords do not match."))
        if User.objects.filter(username=username).exists():
            errors.append(_("Username already exists."))
        if email and User.objects.filter(email=email).exists():
            errors.append(_("Email already exists."))
        if employee_id and Employee.objects.filter(employee_id=employee_id).exists():
            errors.append(_("Employee ID already exists."))

        # ─── “one head per dept” check ───
        if is_head_of_dep and dept_id:
            dept = Department.objects.filter(id=dept_id).first()
            if dept and Employee.objects.filter(department=dept, is_head_of_dep=True).exists():
                errors.append(
                    _("Department “%(dept)s” already has a head.") % {'dept': dept.name}
                )

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            # — everything is good, save both in a transaction —
            with transaction.atomic():
                user = User.objects.create_user(
                    first_name=first_name,
                    last_name=last_name,
                    username=username,
                    email=email,
                    password=password
                )
                user.phone_number = phone_number
                user.gender = gender
                if profile_photo:
                    user.profile_photo = profile_photo
                user.account_type = User.ACCOUNT_TYPE_EMPLOYEE
                user.groups.set(selected_roles)
                user.save()

                dept = Department.objects.filter(id=dept_id).first()
                shift = Shift.objects.filter(id=shift_id).first()

                Employee.objects.create(
                    user=user,
                    employee_id=employee_id or default_employee_id,
                    father_name=father_name,
                    grand_father_name=grand_father_name,
                    position=position,
                    is_device_admin=is_device_admin,
                    bast=bast,
                    qua_dam=qua_dam,
                    legacy_code=legacy_code,
                    department=dept,
                    shift=shift,
                    work_type=work_type,
                    salary=salary_val,
                    contract_date=contract_date,
                    education_degree=education_degree,
                    national_id=national_id,
                    duty_days=duty_days,
                    extra_info=extra_info,
                    is_head_of_dep=is_head_of_dep,
                    address=address,
                )

            messages.success(request, _("Employee “%(name)s” added.") % {'name': user.get_full_name() or user.username})
            return redirect('employees')

    return render(request, 'employees/add_employee.html', {
        'departments': departments,
        'shifts': shifts,
        'work_types': work_types,
        'roles': roles,
        'old': old,
        'default_employee_id': default_employee_id,
    })

@login_required(login_url='login')
@permission_required('core.change_employee', raise_exception=True)
def edit_employee(request, employee_id):
    emp = get_object_or_404(Employee, id=employee_id)
    user = emp.user
    departments = Department.objects.all()
    shifts = Shift.objects.filter(is_active=True)
    work_types = Employee.WORK_TYPE_CHOICES
    roles = Group.objects.all()

    # ── Build “old” dict for form‐prefill ────────────────────────
    if request.method == 'POST':
        old = request.POST.copy()
    else:
        old = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'father_name': emp.father_name,
            'grand_father_name': emp.grand_father_name,
            'position': emp.position,
            'is_device_admin': 'on' if emp.is_device_admin else '',
            'employee_id': emp.employee_id,
            'username': user.username,
            'email': user.email or '',
            'password': '',
            'confirm_password': '',
            'gender': user.gender,
            'phone_number': user.phone_number or '',
            'department': str(emp.department.id) if emp.department else '',
            'is_head_of_dep': 'on' if emp.is_head_of_dep else '',
            'roles': str(user.groups.first().id) if user.groups.exists() else '',
            'shift': str(emp.shift.id) if emp.shift else '',
            'work_type': emp.work_type,
            'duty_days': str(emp.duty_days),
            'bast': emp.bast,
            'qua_dam': emp.qua_dam,
            'legacy_code': emp.legacy_code,
            'salary': emp.salary if emp.salary is not None else '',
            'contract_date': emp.contract_date or '',
            'education_degree': emp.education_degree or '',
            'national_id': emp.national_id or '',
            'address': emp.address or '',
            'extra_info': emp.extra_info,
        }

    if request.method == 'POST':
        # ── Pull everything out ────────────────────────────────
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        father_name = request.POST.get('father_name', '').strip()
        grand_father = request.POST.get('grand_father_name', '').strip()
        position = request.POST.get('position', '').strip()
        is_device_admin = bool(request.POST.get('is_device_admin'))
        emp_id_val = request.POST.get('employee_id', '').strip()
        username_val = request.POST.get('username', '').strip()
        email_val = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        gender_val = request.POST.get('gender', '')
        phone_val = request.POST.get('phone_number', '').strip()
        profile_photo = request.FILES.get('profile_photo')
        selected_role = request.POST.get('roles')
        dept_id = request.POST.get('department')
        is_head = bool(request.POST.get('is_head_of_dep'))
        address = request.POST.get('address', '').strip()
        shift_id = request.POST.get('shift')
        work_type = request.POST.get('work_type', Employee.FULL_TIME)
        duty_days = request.POST.get('duty_days') or 0
        bast = request.POST.get('bast', '').strip()
        qua_dam = request.POST.get('qua_dam', '').strip()
        legacy_code = request.POST.get('legacy_code', '').strip()
        salary_val = request.POST.get('salary') or None
        contract_date = request.POST.get('contract_date', '').strip()
        education_deg = request.POST.get('education_degree', '').strip()
        national_id = request.POST.get('national_id', '').strip()
        extra_info = request.POST.get('extra_info', '').strip()

        old = request.POST.copy()

        # ── Validation ────────────────────────────────────────
        errors = []

        # optional password change
        if password or confirm_password:
            if password != confirm_password:
                errors.append(_("Passwords do not match."))

        if User.objects.exclude(id=user.id).filter(username=username_val).exists():
            errors.append(_("Username already exists."))
        if email_val and User.objects.exclude(id=user.id).filter(email=email_val).exists():
            errors.append(_("Email already exists."))
        if emp_id_val and Employee.objects.exclude(id=emp.id).filter(employee_id=emp_id_val).exists():
            errors.append(_("Employee ID already exists."))
        # single head per department
        if is_head and dept_id:
            dept = Department.objects.filter(id=dept_id).first()
            if dept and Employee.objects.exclude(id=emp.id) \
                    .filter(department=dept, is_head_of_dep=True).exists():
                errors.append(
                    _("Department “%(dept)s” already has a head.") % {'dept': dept.name}
                )

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            # ── All good, save ───────────────────────────────
            with transaction.atomic():
                # — update User —
                user.first_name = first_name
                user.last_name = last_name
                user.username = username_val
                user.email = email_val
                user.gender = gender_val
                user.phone_number = phone_val
                if profile_photo:
                    user.profile_photo = profile_photo
                # only change if provided
                if password and password == confirm_password:
                    user.set_password(password)
                if selected_role:
                    user.groups.set([selected_role])
                else:
                    user.groups.clear()
                user.save()

                # — update Employee —
                emp.employee_id = emp_id_val
                emp.father_name = father_name
                emp.grand_father_name = grand_father
                emp.position = position
                emp.is_device_admin = is_device_admin
                emp.department = Department.objects.filter(id=dept_id).first()
                emp.shift = Shift.objects.filter(id=shift_id).first()
                emp.work_type = work_type
                emp.duty_days = duty_days
                emp.bast = bast
                emp.qua_dam = qua_dam
                emp.legacy_code = legacy_code
                emp.salary = salary_val
                emp.contract_date = contract_date
                emp.education_degree = education_deg
                emp.national_id = national_id
                emp.address = address
                emp.extra_info = extra_info
                emp.is_head_of_dep = is_head
                emp.save()

            messages.success(
                request,
                _("Employee “%(name)s” updated.") % {
                    'name': user.get_full_name() or user.username
                }
            )
            return redirect('employees')

    return render(request, 'employees/edit_employee.html', {
        'departments': departments,
        'shifts': shifts,
        'work_types': work_types,
        'roles': roles,
        'old': old,
        'employee': emp,
    })

@login_required(login_url='login')
@permission_required('core.delete_employee', raise_exception=True)
@csrf_exempt
def delete_employee(request):
    """
    AJAX endpoint to delete an Employee *and* its related User account.
    """
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        emp_id = request.POST.get('id')
        try:
            emp = Employee.objects.get(id=emp_id)
            # Deleting the User will cascade and remove the Employee record too
            emp.user.delete()
            return JsonResponse({'success': True})
        except Employee.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': _("Employee not found.")
            }, status=404)

    return JsonResponse({
        'success': False,
        'error': _("Invalid request.")
    }, status=400)

@login_required(login_url='login')
@permission_required('core.view_department_list', raise_exception=True)
def departments(request):
    return render(request, "departments/departments.html")  # template in employee/templates/employee/

@login_required(login_url='login')
@permission_required('core.view_department_list', raise_exception=True)
def fetch_departments(request):
    if request.method != 'POST':
        return JsonResponse({'error': _("Invalid request method.")}, status=400)

    page = int(request.POST.get('page', 1))
    page_size = int(request.POST.get('page_size', 10))
    search_val = request.POST.get('search_value', '').strip().lower()
    order_by = request.POST.get('order_by', 'id')
    order_dir = request.POST.get('order_dir', 'asc').lower()

    # ─── 1) Annotate both active and archived employee counts ───────────────
    qs = Department.objects.annotate(
        employee_count=Count('employees', filter=Q(employees__is_archive=False)),
        archived_count=Count('employees', filter=Q(employees__is_archive=True)),
    )
    total_records = qs.count()

    # ─── 2) search by name ────────────────────────────────────────────────
    if search_val:
        qs = qs.filter(name__icontains=search_val)
    total_filtered = qs.count()

    # ─── 3) map DataTables → ORM fields (including archived_count) ────────
    key_map = {
        'id': 'id',
        'name': 'name',
        'employee_count': 'employee_count',
        'archived_count': 'archived_count',
        'updated_at': 'updated_at',
    }
    orm_field = key_map.get(order_by, 'id')
    prefix = '-' if order_dir == 'desc' else ''
    qs = qs.order_by(f'{prefix}{orm_field}')

    # ─── 4) paginate ─────────────────────────────────────────────────────
    page_obj = Paginator(qs, page_size).get_page(page)

    # ─── 5) build JSON ───────────────────────────────────────────────────
    data = []
    for dept in page_obj:
        data.append({
            'id': dept.id,
            'name': dept.name,
            'employee_count': dept.employee_count,
            'archived_count': dept.archived_count,
            'updated_at': jalali_datetime_str(dept.updated_at) if dept.updated_at else '',
        })

    return JsonResponse({
        'recordsTotal': total_records,
        'recordsFiltered': total_filtered,
        'data': data,
    })

@login_required(login_url='login')
@permission_required('core.add_department', raise_exception=True)
def add_department(request):
    """
    Create a new Department.
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()

        if not name:
            messages.error(request, _("Department name is required."))
        elif Department.objects.filter(name__iexact=name).exists():
            messages.error(request, _("A department with that name already exists."))
        else:
            Department.objects.create(name=name)
            messages.success(request, _("Department “%(name)s” created.") % {'name': name})
            return redirect('departments')

    # either GET or invalid POST
    return render(request, 'departments/add_department.html', {})

@login_required(login_url='login')
@permission_required('core.change_department', raise_exception=True)
def edit_department(request, dept_id):
    """
    Edit an existing Department.
    """
    dept = get_object_or_404(Department, id=dept_id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()

        # Validation
        if not name:
            messages.error(request, _("Department name is required."))
        elif Department.objects.exclude(id=dept.id).filter(name__iexact=name).exists():
            messages.error(request, _("A department with that name already exists."))
        else:
            dept.name = name
            dept.save()
            messages.success(
                request,
                _("Department “%(name)s” has been updated.") % {'name': name}
            )
            return redirect('departments')

    # On GET or validation error, render form with current data
    return render(request, 'departments/edit_department.html', {
        'dept': dept,
    })

@login_required(login_url='login')
@permission_required('core.delete_department', raise_exception=True)
@csrf_exempt
def delete_department(request):
    """
    AJAX-only endpoint to delete a department, but only if no employees
    are still assigned to it.
    """
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        dept_id = request.POST.get('id')
        try:
            dept = Department.objects.get(id=dept_id)
            # if you set related_name='employees' on the FK in Employee:
            if dept.employees.exists():
                return JsonResponse({
                    'success': False,
                    'error': _("Cannot delete department: it’s still assigned to one or more employees.")
                }, status=400)

            dept.delete()
            return JsonResponse({'success': True})

        except Department.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': _("Department not found.")
            }, status=404)

    return JsonResponse({
        'success': False,
        'error': _("Invalid request.")
    }, status=400)

@login_required(login_url='login')
@permission_required('core.view_shift_list', raise_exception=True)
def shifts(request):
    return render(request, 'shifts/shifts.html')

@login_required(login_url='login')
@permission_required('core.view_shift_list', raise_exception=True)
def fetch_shifts(request):
    if request.method != 'POST':
        return JsonResponse({'error': _("Invalid request method.")}, status=400)

    page = int(request.POST.get('page', 1))
    page_size = int(request.POST.get('page_size', 10))
    search_val = request.POST.get('search_value', '').strip()
    order_by = request.POST.get('order_by', 'id')
    order_dir = request.POST.get('order_dir', 'asc').lower()

    # ─── 1) Annotate both active & archived employee counts ─────────────
    qs = Shift.objects.annotate(
        employee_count=Count('employee', filter=Q(employee__is_archive=False)),
        archived_count=Count('employee', filter=Q(employee__is_archive=True)),
    )
    total_records = qs.count()

    # ─── 2) Search by shift name ────────────────────────────────────────
    if search_val:
        qs = qs.filter(name__icontains=search_val)
    total_filtered = qs.count()

    # ─── 3) Map DataTables columns → ORM fields ────────────────────────
    key_map = {
        'id': 'id',
        'name': 'name',
        'employee_count': 'employee_count',
        'archived_count': 'archived_count',
        'updated_at': 'updated_at',
    }
    orm_field = key_map.get(order_by, 'id')
    prefix = '-' if order_dir == 'desc' else ''
    qs = qs.order_by(f'{prefix}{orm_field}')

    # ─── 4) Paginate ───────────────────────────────────────────────────
    page_obj = Paginator(qs, page_size).get_page(page)

    # ─── 5) Build JSON ─────────────────────────────────────────────────
    data = []
    for shift in page_obj:
        data.append({
            'id': shift.id,
            'name': shift.name,
            'employee_count': shift.employee_count,
            'archived_count': shift.archived_count,
            'updated_at': jalali_datetime_str(shift.updated_at) if shift.updated_at else '',
        })

    return JsonResponse({
        'recordsTotal': total_records,
        'recordsFiltered': total_filtered,
        'data': data,
    })

@login_required(login_url='login')
@permission_required('core.view_shift_list', raise_exception=True)
def fetch_shift_years(request):
    """
    AJAX: given ?shift_id=NNN, return all the distinct years
    for which that shift has schedules, in ascending order.
    """
    shift_id = request.GET.get('shift_id')
    shift = get_object_or_404(Shift, pk=shift_id)
    years = (
        ShiftSchedule.objects
        .filter(shift=shift)
        .values_list('year', flat=True)
        .distinct()
        .order_by('year')
        .reverse()
    )
    return JsonResponse({'years': list(years)})

@login_required(login_url='login')
@permission_required('core.view_shift_list', raise_exception=True)
@require_POST
def add_shift_year(request):
    shift_id = request.POST.get('shift_id')
    new_year = request.POST.get('year')
    shift = get_object_or_404(Shift, pk=shift_id)

    # validate year
    try:
        new_year = int(new_year)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': _('Invalid year')}, status=400)

    existing_years = list(
        ShiftSchedule.objects.filter(shift=shift)
        .values_list('year', flat=True)
        .distinct()
    )
    if new_year in existing_years:
        return JsonResponse({'success': False, 'error': _('Year already exists')}, status=400)

    if not existing_years:
        return JsonResponse({'success': False, 'error': _('No existing template year to copy from')}, status=400)

    # pick the max year to copy from
    source_year = max(existing_years)

    # duplicate all schedules for source_year into new_year
    with transaction.atomic():
        templates = ShiftSchedule.objects.filter(shift=shift, year=source_year)
        clones = []
        for tpl in templates:
            clones.append(ShiftSchedule(
                shift=tpl.shift,
                year=new_year,
                month=tpl.month,
                day_of_week=tpl.day_of_week,
                in_start_time=tpl.in_start_time,
                in_end_time=tpl.in_end_time,
                out_start_time=tpl.out_start_time,
                out_end_time=tpl.out_end_time,
                author=request.user,
                is_active=tpl.is_active,
            ))

        # reset PK sequence to avoid duplicate-key errors
        table = ShiftSchedule._meta.db_table
        sql = (
                "SELECT setval(pg_get_serial_sequence('%s', 'id'),"
                " (SELECT COALESCE(MAX(id), 1) FROM %s))" % (table, table)
        )
        with connection.cursor() as cursor:
            cursor.execute(sql)

        ShiftSchedule.objects.bulk_create(clones)

    return JsonResponse({'success': True})

@login_required(login_url='login')
@permission_required('core.view_shift_list', raise_exception=True)
@require_POST
def delete_shift_year(request):
    shift_id = request.POST.get('shift_id')
    year = request.POST.get('year')
    shift = get_object_or_404(Shift, pk=shift_id)

    # get all distinct years
    years = list(
        ShiftSchedule.objects.filter(shift=shift)
        .values_list('year', flat=True)
        .distinct()
    )
    try:
        year = int(year)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': _('Invalid year')}, status=400)

    if year not in years:
        return JsonResponse({'success': False, 'error': _('Year not found')}, status=404)
    if len(years) <= 1:
        return JsonResponse({'success': False, 'error': _('Cannot delete the only year')}, status=400)

    # delete all schedules for that year
    ShiftSchedule.objects.filter(shift=shift, year=year).delete()
    return JsonResponse({'success': True})

@login_required(login_url='login')
@permission_required('core.add_shift', raise_exception=True)
def add_shift(request):
    """
    Create a new Shift (just name + author), and seed 12×7 blank schedules—
    with Fridays inactive by default.
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()

        # validation
        if not name:
            messages.error(request, _("Shift name is required."))
        elif Shift.objects.filter(name__iexact=name).exists():
            messages.error(request, _("A shift with that name already exists."))
        else:
            with transaction.atomic():
                shift = Shift.objects.create(name=name, author=request.user)
                # Fix Shift sequence to avoid duplicate key errors
                table = Shift._meta.db_table
                seq_sql = (
                              "SELECT setval(pg_get_serial_sequence('%s', 'id'), "
                              "(SELECT COALESCE(MAX(id), 1) FROM %s))"
                          ) % (table, table)

                with connection.cursor() as cursor:
                    cursor.execute(seq_sql)

                current_date = get_today_persian_date()
                schedules = []
                friday_value = ShiftSchedule.DayOfWeek.FRIDAY  # == 7

                for month in range(1, 13):
                    for day in range(1, 8):
                        schedules.append(ShiftSchedule(
                            shift=shift,
                            year=current_date.year,
                            month=month,
                            day_of_week=day,
                            author=request.user,
                            is_active=(day != friday_value),
                            # in_*/out_* times left NULL for later editing
                        ))
                ShiftSchedule.objects.bulk_create(schedules)

            messages.success(request, _("Shift “%(name)s” created.") % {'name': name})
            return redirect('shifts')

    return render(request, 'shifts/add_shift.html')

@login_required(login_url='login')
@permission_required('core.change_shift', raise_exception=True)
def edit_shift(request, shift_id):
    """
    Edit an existing Shift’s name.
    """
    shift = get_object_or_404(Shift, id=shift_id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()

        # Validation
        if not name:
            messages.error(request, _("Shift name is required."))
        elif Shift.objects.exclude(id=shift.id).filter(name__iexact=name).exists():
            messages.error(request, _("A shift with that name already exists."))
        else:
            shift.name = name
            shift.save()
            messages.success(request, _("Shift “%(name)s” has been updated.") % {'name': name})
            return redirect('shifts')

    return render(request, 'shifts/edit_shift.html', {
        'shift': shift,
    })

@login_required(login_url='login')
@permission_required('core.delete_shift', raise_exception=True)
@csrf_exempt
def delete_shift(request):
    """
    AJAX-only: delete a Shift and all its ShiftSchedule entries.
    Prevent if any employees are still assigned.
    """
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        shift_id = request.POST.get('id')
        shift = get_object_or_404(Shift, id=shift_id)

        # Prevent deletion if any employees reference this shift
        if shift.employee_set.exists():
            return JsonResponse({
                'success': False,
                'error': _("Cannot delete shift: one or more employees are assigned to it.")
            }, status=400)

        # Atomically delete schedules then the shift
        with transaction.atomic():
            ShiftSchedule.objects.filter(shift=shift).delete()
            shift.delete()

        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': _("Invalid request")}, status=400)

@login_required(login_url='login')
@permission_required('core.change_shift', raise_exception=True)
def view_shift(request, shift_id):
    shift = get_object_or_404(Shift, id=shift_id)
    # get year from querystring or default to current
    try:
        year = int(request.GET.get('year', date.today().year))
    except ValueError:
        year = date.today().year

    # grab all schedules for that shift & year
    qs = ShiftSchedule.objects.filter(shift=shift, year=year).order_by('month', 'day_of_week')

    # if the form was submitted, process updates
    if request.method == 'POST':
        for sched in qs:
            # parse times (could be blank)
            for fld in ('in_start_time', 'in_end_time', 'out_start_time', 'out_end_time'):
                val = request.POST.get(f'{fld}_{sched.id}')
                setattr(sched, fld, datetime.strptime(val, '%H:%M').time() if val else None)
            # active flag
            sched.is_active = request.POST.get(f'active_{sched.id}') == 'on'
            sched.save()
        messages.success(request, _("Shift schedule for %(year)s updated.") % {'year': year})
        # redirect to clean the POST
        return redirect(f"{reverse('view_shift', args=[shift_id])}?year={year}")

    # organize by month
    months = []
    for idx, name in enumerate(PERSIAN_MONTHS, start=1):
        months.append({
            'num': idx,
            'name': _(name),
            'schedules': qs.filter(month=idx)
        })

    return render(request, 'shifts/view_shift.html', {
        'shift': shift,
        'year': year,
        'months': months,
        'years_available': ShiftSchedule.objects
                  .filter(shift=shift)
                  .values_list('year', flat=True)
                  .distinct()
                  .order_by('year'),
    })
