from collections import defaultdict
from datetime import datetime, date
from datetime import timedelta
from time import sleep

import jdatetime
from django.contrib import messages
from django.contrib.auth.decorators import permission_required, login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Max, Sum, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.templatetags.static import static
from django.utils import timezone
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from config.constants import MIN_YEAR, PERSIAN_MONTHS, LEAVE_LIMITS, PY_TO_SS_DOW_GREGORIAN, PY_TO_SS_DOW_JALALI
from core.utils import get_daily_attendance, get_monthly_attendance, get_attendance_summary, chunked
from employee.models import Department, ShiftSchedule, Shift
from employee.models import Employee
from libraries.pdate.calendar_utils import jalali_datetime_str
from notifications.utils import notify_send
from users.models import User
from vendors.build.manager import set_user_templates, is_device_online, DeviceConfig, delete_user_templates, delete_user_card, set_user, get_user_templates, get_user, upload_users_with_templates_hr, delete_device_data, set_device_time, get_device_info, get_device_time, build_emp_finger, build_emp_user
from .models import AttendanceLog, BiometricRecord
from .models import Device, DailyLeave
from .models import EmployeeVacation


@login_required(login_url='login')
@permission_required('core.view_device_list', raise_exception=True)
def devices(request):
    device = Device.objects.all()
    return render(request, "attendance/devices.html", {'devices': device})


@login_required(login_url='login')
@permission_required('core.add_device', raise_exception=True)
def add_device(request):
    """
    Create a new Device.
    """
    device_types = Device.DeviceType.choices
    status_choices = Device.Status.choices

    form_data = {}  # renamed so it can't collide with `messages`

    if request.method == 'POST':
        # — pull & sanitize —
        identifier = request.POST.get('identifier', '').strip()
        name = request.POST.get('name', '').strip()
        ip_address = request.POST.get('ip_address', '').strip()
        port_raw = request.POST.get('port', '').strip()
        com_key_raw = request.POST.get('com_key', '').strip()
        dtype = request.POST.get('device_type', '')
        status = request.POST.get('status', '')
        description = request.POST.get('description', '').strip()

        # keep form values to re-populate on error
        form_data = request.POST.copy()

        # — validate —
        errors = []
        if not identifier:
            errors.append(_("Device ID is required."))
        elif Device.objects.filter(identifier=identifier).exists():
            errors.append(_("A device with that ID already exists."))

        if not name:
            errors.append(_("Device name is required."))

        try:
            port = int(port_raw)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            errors.append(_("Port must be a number between 1 and 65535."))

        try:
            com_key = int(com_key_raw)
        except ValueError:
            errors.append(_("COM Key must be a number."))

        valid_types = [choice[0] for choice in device_types]
        valid_status = [choice[0] for choice in status_choices]
        if dtype not in valid_types:
            errors.append(_("Invalid device type selected."))
        if status not in valid_status:
            errors.append(_("Invalid status selected."))

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            # — all good, create in a transaction —
            with transaction.atomic():
                Device.objects.create(
                    identifier=identifier,
                    name=name,
                    ip_address=ip_address,
                    port=port,
                    com_key=com_key,
                    device_type=dtype,
                    status=status,
                    description=description,
                )
            messages.success(request, _("Device “%(dev)s” added.") % {'dev': name})
            return redirect('devices')

    return render(request, 'attendance/add_device.html', {
        'device_types': device_types,
        'status_choices': status_choices,
        'old': form_data,  # to re-populate your form
    })


@login_required(login_url='login')
@permission_required('core.change_device', raise_exception=True)
def edit_device(request, device_id):
    """
    Edit an existing Device.
    """
    device = get_object_or_404(Device, id=device_id)
    device_types = Device.DeviceType.choices
    status_choices = Device.Status.choices

    # start with the device’s current values
    form_data = {
        'identifier': device.identifier,
        'name': device.name,
        'ip_address': device.ip_address,
        'port': device.port,
        'com_key': device.com_key,
        'device_type': device.device_type,
        'status': device.status,
        'description': device.description,
    }

    if request.method == 'POST':
        # pull & sanitize
        identifier = request.POST.get('identifier', '').strip()
        name = request.POST.get('name', '').strip()
        ip_address = request.POST.get('ip_address', '').strip()
        port_raw = request.POST.get('port', '').strip()
        com_key_raw = request.POST.get('com_key', '').strip()
        dtype = request.POST.get('device_type', '')
        status = request.POST.get('status', '')
        description = request.POST.get('description', '').strip()

        # keep form values for re-render
        form_data = request.POST.copy()

        # validate
        errors = []
        if not identifier:
            errors.append(_("Device ID is required."))
        elif Device.objects.exclude(id=device.id).filter(identifier=identifier).exists():
            errors.append(_("Another device with that ID already exists."))

        if not name:
            errors.append(_("Device name is required."))

        try:
            port = int(port_raw)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            errors.append(_("Port must be a number between 1 and 65535."))

        try:
            com_key = int(com_key_raw)
        except ValueError:
            errors.append(_("COM Key must be a number."))

        valid_types = [c[0] for c in device_types]
        valid_status = [c[0] for c in status_choices]
        if dtype not in valid_types:
            errors.append(_("Invalid device type selected."))
        if status not in valid_status:
            errors.append(_("Invalid status selected."))

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            # all good → save
            with transaction.atomic():
                device.identifier = identifier
                device.name = name
                device.ip_address = ip_address
                device.port = port
                device.com_key = com_key
                device.device_type = dtype
                device.status = status
                device.description = description
                device.save()

            messages.success(request, _("Device “%(dev)s” updated.") % {'dev': name})
            return redirect('devices')

    return render(request, 'attendance/edit_device.html', {
        'device': device,
        'device_types': device_types,
        'status_choices': status_choices,
        'old': form_data,
    })


@login_required(login_url='login')
@permission_required('core.delete_device', raise_exception=True)
@csrf_exempt
def delete_device(request):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        dev_id = request.POST.get('id')
        try:
            dev = get_object_or_404(Device, id=dev_id)
            dev.delete()
            return JsonResponse({'success': True})
        except Exception:
            return JsonResponse({'success': False, 'error': _("Could not delete device.")}, status=400)

    return JsonResponse({'success': False, 'error': _("Invalid request.")}, status=400)


@login_required(login_url='login')
@permission_required('core.view_device', raise_exception=True)
def view_device(request, device_id):
    device = get_object_or_404(Device, id=device_id)
    return render(request, 'attendance/view_device.html', {'device': device})


@login_required(login_url='login')
@permission_required('core.view_device', raise_exception=True)
def fetch_device_stats(request, device_id):
    device = get_object_or_404(Device, id=device_id)

    # If device is disabled → return zeros and skip
    if device.status == Device.Status.DISABLED:
        data = {
            "users": {"used": 0, "cap": 0},
            "fingers": {"used": 0, "cap": 0},
            "faces": {"used": 0, "cap": 0},
            "cards": {"used": 0, "cap": 0},
        }
        return JsonResponse({"success": True, "data": data, "skip": True})

    cfg = DeviceConfig(ip=device.ip_address, port=device.port, com_key=device.com_key)

    try:
        info = get_device_info(cfg)

        # If info is None or missing counts, treat as failure
        if not info or "counts" not in info:
            raise ValueError("Invalid or incomplete device response")

        counts = info.get("counts", {})
        data = {
            "users": {"used": counts.get("users", 0), "cap": counts.get("users_cap", 0)},
            "fingers": {"used": counts.get("fingers", 0), "cap": counts.get("fingers_cap", 0)},
            "faces": {"used": counts.get("faces", 0), "cap": counts.get("faces_cap", 0)},
            "cards": {"used": counts.get("cards", 0), "cap": counts.get("users_cap", 0)},  # card cap = user cap
        }
        return JsonResponse({"success": True, "data": data})

    except Exception as e:
        # On any failure, safely return all zeros
        data = {
            "users": {"used": 0, "cap": 0},
            "fingers": {"used": 0, "cap": 0},
            "faces": {"used": 0, "cap": 0},
            "cards": {"used": 0, "cap": 0},
        }
        return JsonResponse({"success": True, "data": data, "error": str(e)})


@login_required(login_url='login')
@permission_required('core.view_device', raise_exception=True)
def check_device_status(request, device_id):
    device = get_object_or_404(Device, id=device_id)

    if device.status == Device.Status.DISABLED:
        return JsonResponse({'skip': True})

    cfg = DeviceConfig(ip=device.ip_address, port=device.port, com_key=device.com_key)
    try:
        online = is_device_online(cfg)
        response = {'online': online}
        if online:
            dt = get_device_time(cfg)
            response['device_time'] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        return JsonResponse(response)
    except Exception as e:
        return JsonResponse({'online': False, 'error': str(e)})


@login_required(login_url='login')
@permission_required('core.view_device', raise_exception=True)
@require_POST
def sync_devices_time(request):
    devices = Device.objects.filter(status=Device.Status.ENABLED)
    if not devices.exists():
        return JsonResponse({'success': False, 'error': 'No enabled devices found.'})

    failed = []
    synced = []
    current_time = now().replace(microsecond=0)

    for dev in devices:
        cfg = DeviceConfig(ip=dev.ip_address, port=dev.port, com_key=dev.com_key)
        try:
            if not is_device_online(cfg):
                failed.append(dev.name)
                continue
            success = set_device_time(cfg, current_time)
            if success:
                synced.append(dev.name)
            else:
                failed.append(dev.name)
        except Exception as e:
            failed.append(dev.name)

    if failed and not synced:
        return JsonResponse({'success': False, 'error': f"Failed to sync any devices. Offline or error: {', '.join(failed)}"})

    msg = f"Synced {len(synced)} devices."
    if failed:
        msg += f" Failed: {', '.join(failed)}"
    return JsonResponse({'success': True, 'message': msg})


@login_required(login_url='login')
@permission_required('core.view_device', raise_exception=True)
def delete_device_users(request):
    device_id = request.POST.get('device_id')

    try:
        device = Device.objects.get(id=device_id)

        if device.status == Device.Status.DISABLED:
            return JsonResponse({'success': False, 'error': _('Device is disabled.')})

        cfg = DeviceConfig(ip=device.ip_address, port=device.port, com_key=device.com_key)

        if not is_device_online(cfg):
            return JsonResponse({'success': False, 'error': _('Device is offline.')})

        status = delete_device_data(cfg, clear_all=True)

        if status:
            return JsonResponse({'success': True, 'message': _('Users deleted successfully from device.')})
        else:
            return JsonResponse({'success': False, 'error': _('Failed to delete data from device.')})

    except Device.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Device not found.')})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='login')
def check_upload_progress(request):
    task_id = request.GET.get('task_id')
    data = cache.get(task_id, {})
    return JsonResponse({
        'progress': data.get('progress', 0),
        'status': data.get('status', 'working')  # 'success', 'error', or 'working'
    })


@login_required(login_url='login')
@require_POST
@permission_required('core.view_employee_biometric', raise_exception=True)
def upload_all_biometrics_to_device(request):
    device_id = request.POST.get("device_id")
    task_id = request.POST.get("task_id")

    # 1) Validate device
    try:
        device = Device.objects.get(id=device_id)
    except Device.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Device not found.')})

    if device.status == Device.Status.DISABLED:
        return JsonResponse({'success': False, 'error': _('Device is currently disabled.')})

    cfg = DeviceConfig(ip=device.ip_address, port=device.port, com_key=device.com_key, timeout=400)
    if not is_device_online(cfg):
        return JsonResponse({'success': False, 'error': _('Device "%(name)s" is offline.') % {'name': device.name}})

    # 2) Fetch biometric-enabled employees
    employees = Employee.objects.filter(is_archive=False)
    total = employees.count()
    processed = 0
    user_template_data = []

    for emp in employees:
        fingerprint_records = emp.biometric_records.filter(
            biometric_type=BiometricRecord.BiometricType.FINGERPRINT
        )
        if not fingerprint_records.exists():
            continue

        # Card info
        card_record = emp.biometric_records.filter(
            biometric_type=BiometricRecord.BiometricType.RFID
        ).order_by('-created_at').first()
        try:
            card = int(card_record.template_data) if card_record else 0
        except (TypeError, ValueError):
            card = 0

        # Build ZKUser
        bio_user = build_emp_user(emp, card)

        fingers = []
        for rec in fingerprint_records:
            try:
                fingers.append(build_emp_finger(emp.employee_id, rec))
            except Exception:
                continue

        user_template_data.append((bio_user, fingers))
        processed += 1

        # ✅ Accurate progress (based on processed user_template_data)
        if task_id:
            progress = round((processed / total) * 100)
            cache.set(task_id, {'progress': min(progress, 99), 'status': 'working'}, timeout=600)

    if not user_template_data:
        return JsonResponse({'success': False, 'error': _('No fingerprint data found to upload.')})

    # 3) Upload to device
    success = upload_users_with_templates_hr(cfg, user_template_data)

    if success:
        if task_id:
            cache.set(task_id, {'progress': 100, 'status': 'success'}, timeout=600)
        return JsonResponse({'success': True, 'message': _('All fingerprint data successfully uploaded to %(name)s.') % {'name': device.name}})
    else:
        if task_id:
            cache.set(task_id, {'progress': 100, 'status': 'error'}, timeout=600)
        return JsonResponse({'success': False, 'error': _('Upload failed. Please check device connection or data integrity.')})


@login_required(login_url='login')
@require_POST
@permission_required('core.view_employee_biometric', raise_exception=True)
def download_biometric_data(request):
    employee_id = request.POST.get('employee_id')
    option = request.POST.get('option')  # 'finger', 'face', 'card'

    # 1) Validate employee
    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Employee not found.')})

    # 2) Get registration devices that are enabled
    registration_devices = Device.objects.filter(
        device_type=Device.DeviceType.REGISTRATION,
        status=Device.Status.ENABLED
    )
    sleep(0.5)

    if not registration_devices.exists():
        return JsonResponse({'success': False, 'error': _('No registration devices available.')})

    # 3) Check online status
    target_dev = None
    for dev in registration_devices:
        cfg = DeviceConfig(ip=dev.ip_address, port=dev.port, com_key=dev.com_key)
        if is_device_online(cfg):
            target_dev = (dev, cfg)
            break

    if not target_dev:
        return JsonResponse({'success': False, 'error': _('No registration device is online.')})

    dev, cfg = target_dev

    # 4) Fingerprint
    if option == "finger":
        templates = get_user_templates(cfg, user_id=employee_id)
        count = 0
        for tpl in templates:
            BiometricRecord.objects.update_or_create(
                employee=employee,
                biometric_type=BiometricRecord.BiometricType.FINGERPRINT,
                finger_position=tpl.get("fid"),
                defaults={
                    "template_data": tpl.get("template"),
                    "device": dev
                }
            )
            count += 1

        if count == 0:
            return JsonResponse({'success': False, 'error': _('No fingerprint templates found for this employee.')})

        return JsonResponse({'success': True, 'message': _('%(count)d Fingerprint templates downloaded.') % {'count': count}})

    # 5) Card
    elif option == "card":
        user = get_user(cfg, user_id=employee_id)
        if user and user.get("card"):
            BiometricRecord.objects.update_or_create(
                employee=employee,
                biometric_type=BiometricRecord.BiometricType.RFID,
                finger_position=None,
                defaults={
                    "template_data": str(user["card"]),
                    "device": dev
                }
            )
            return JsonResponse({'success': True, 'message': _('Card data downloaded successfully.')})
        return JsonResponse({'success': False, 'error': _('No card data found on the device.')})

    # 6) Face
    elif option == "face":
        return JsonResponse({'success': False, 'error': _('Face download is under development.')})

    # 7) Invalid option fallback
    return JsonResponse({'success': False, 'error': _('Invalid biometric option.')})


@login_required(login_url='login')
@require_POST
@permission_required('core.view_employee_biometric', raise_exception=True)
def upload_biometric_data(request):
    employee_id = request.POST.get("employee_id")
    option = request.POST.get("option")  # 'finger', 'face', 'card'

    # 1) Validate employee
    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Employee not found.')})

    # 2) Check biometric records for the selected type
    biometric_type_map = {
        'finger': BiometricRecord.BiometricType.FINGERPRINT,
        'card': BiometricRecord.BiometricType.RFID,
        'face': BiometricRecord.BiometricType.FACE
    }
    sleep(0.5)
    if option not in biometric_type_map:
        return JsonResponse({'success': False, 'error': _('Invalid biometric type.')})

    biometric_type = biometric_type_map[option]
    records = BiometricRecord.objects.filter(employee=employee, biometric_type=biometric_type)

    if not records.exists():
        return JsonResponse({'success': False, 'error': _('No biometric records found for selected type.')})

    # 3) Fetch enabled devices
    devices = Device.objects.filter(status=Device.Status.ENABLED, device_type=Device.DeviceType.ATTENDANCE)
    if not devices.exists():
        return JsonResponse({'success': False, 'error': _('No enabled devices available.')})

    # 4) Check device connectivity
    device_cfgs = []
    for dev in devices:
        cfg = DeviceConfig(ip=dev.ip_address, port=dev.port, com_key=dev.com_key)
        if not is_device_online(cfg):
            return JsonResponse({'success': False, 'error': _('Device "%(name)s" is offline.') % {'name': dev.name}})
        device_cfgs.append((dev, cfg))

    # 5) Determine privilege
    privilege = 14 if employee.is_device_admin else 0  # 14 = admin, 0 = normal user

    # 6) Upload logic
    if biometric_type == BiometricRecord.BiometricType.FINGERPRINT:
        # Convert records to Finger objects
        fingers = []
        for rec in records:
            finger = build_emp_finger(employee_id, rec)
            fingers.append(finger)

        uploaded = 0
        for dev, cfg in device_cfgs:
            if set_user_templates(cfg, user_id=employee_id, templates=fingers):
                uploaded += 1

        if uploaded == 0:
            return JsonResponse({'success': False, 'error': _('Failed to upload fingerprint templates.')})
        return JsonResponse({'success': True, 'message': _('%(count)d Fingerprint templates uploaded.') % {'count': uploaded}})


    elif biometric_type == BiometricRecord.BiometricType.RFID:
        # Use latest card record
        card_record = records.order_by('-created_at').first()
        try:
            card_number = int(card_record.template_data)
        except ValueError:
            return JsonResponse({'success': False, 'error': _('Invalid card number format.')})

        uploaded = 0
        for dev, cfg in device_cfgs:
            if set_user(cfg, user_id=str(employee_id), name='', privilege=privilege, card=card_number):
                uploaded += 1

        if uploaded == 0:
            return JsonResponse({'success': False, 'error': _('Failed to upload card data.')})
        return JsonResponse({'success': True, 'message': _('Card uploaded to %(count)d devices.') % {'count': uploaded}})

    elif biometric_type == BiometricRecord.BiometricType.FACE:
        return JsonResponse({'success': False, 'error': _('Face upload is under development.')})

    return JsonResponse({'success': False, 'error': _('Unhandled biometric type.')})


@login_required(login_url='login')
@require_POST
@permission_required('core.view_employee_biometric', raise_exception=True)
def delete_biometric_data(request):
    employee_id = request.POST.get("employee_id")
    option = request.POST.get("option")  # 'finger', 'face', 'card'

    if not employee_id or option not in ("finger", "card", "face"):
        return JsonResponse({'success': False, 'error': _('Invalid request.')})

    # 1) Check if employee exists
    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Employee not found.')})

    # 2) Get enabled attendance devices
    devices = Device.objects.filter(
        status=Device.Status.ENABLED,
        device_type=Device.DeviceType.ATTENDANCE
    )

    sleep(0.5)

    if not devices.exists():
        return JsonResponse({'success': False, 'error': _('No active attendance devices found.')})

    # 3) Check if all are online
    device_cfgs = []
    for dev in devices:
        cfg = DeviceConfig(ip=dev.ip_address, port=dev.port, com_key=dev.com_key)
        if not is_device_online(cfg):
            return JsonResponse({'success': False, 'error': _('Device "%(name)s" is offline.') % {'name': dev.name}})
        device_cfgs.append(cfg)

    # 4) Delete fingerprint data
    if option == "finger":
        deleted = 0
        for cfg in device_cfgs:
            result = delete_user_templates(cfg, user_id=employee_id)
            if result:  # result is a dict of fid → bool
                deleted += 1

        if deleted == 0:
            return JsonResponse({'success': False, 'error': _('Failed to delete fingerprint templates.')})
        return JsonResponse({'success': True, 'message': _('Fingerprint templates deleted from %(count)d devices.') % {'count': deleted}})

    # 5) Delete card data
    elif option == "card":
        deleted = 0
        for cfg in device_cfgs:
            test = delete_user_card(cfg, user_id=employee_id)
            if delete_user_card(cfg, user_id=employee_id):
                deleted += 1

        if deleted == 0:
            return JsonResponse({'success': False, 'error': _('Failed to delete card data.')})
        return JsonResponse({'success': True, 'message': _('Card data removed from %(count)d devices.') % {'count': deleted}})

    # 6) Face – Not implemented yet
    elif option == "face":
        return JsonResponse({'success': False, 'error': _('Face deletion is under development.')})

    return JsonResponse({'success': False, 'error': _('Unknown biometric type.')})


@login_required(login_url='login')
@require_POST
@permission_required('core.delete_employee', raise_exception=True)
def delete_biometric_db(request):
    employee_id = request.POST.get("employee_id")
    option = request.POST.get("option")

    # 1) Validate employee existence
    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Employee not found.')})

    # 2) Validate biometric type
    biometric_type_map = {
        'finger': BiometricRecord.BiometricType.FINGERPRINT,
        'card': BiometricRecord.BiometricType.RFID,
        'face': BiometricRecord.BiometricType.FACE,
    }

    sleep(0.5)

    if option not in biometric_type_map:
        return JsonResponse({'success': False, 'error': _('Invalid biometric type.')})

    biometric_type = biometric_type_map[option]

    # 3) Check if records exist
    records = BiometricRecord.objects.filter(employee=employee, biometric_type=biometric_type)
    if not records.exists():
        return JsonResponse({'success': False, 'error': _('No biometric records found for this employee.')})

    # 4) Delete records
    count = records.count()
    records.delete()

    return JsonResponse({
        'success': True,
        'message': _('%(count)d Biometric records deleted successfully.') % {'count': count}
    })


#  ---------------------- public holiday & employee leave ----------------------
@login_required(login_url='login')
@permission_required('core.view_public_holiday_list', raise_exception=True)
def public_holidays(request):
    today = date.today()
    jtoday = jdatetime.date.fromgregorian(date=today)
    years = list(range(MIN_YEAR, jtoday.year + 2))[::-1]  # descending
    months = PERSIAN_MONTHS  # e.g. ['Hamal', ...]
    # determine current Jalali year & month for defaults:
    return render(request, "attendance/public_holidays.html", {
        "years": years,
        "months": list(enumerate(months, start=1)),  # [(1,'Hamal'),...]
        "current_year": jtoday.year,
        "current_month": jtoday.month,
    })


@login_required(login_url='login')
@permission_required('core.view_public_holiday_list', raise_exception=True)
def fetch_public_holidays(request):
    if request.method != 'POST':
        return JsonResponse({'error': _("Invalid request method.")}, status=400)

    page = int(request.POST.get('page', 1))
    page_size = int(request.POST.get('page_size', 10))
    search_val = request.POST.get('search_value', '').strip().lower()
    order_by = request.POST.get('order_by', 'start_date')
    order_dir = request.POST.get('order_dir', 'desc')
    filter_year = request.POST.get('filter_year')
    filter_mon = request.POST.get('filter_month')

    # 1) build grouped list
    qs = (
        EmployeeVacation.objects
        .filter(type=EmployeeVacation.VacationType.GENERAL_HOLIDAY)
        .values('start_date', 'end_date', 'reason')
        .annotate(days=Max('days_requested'))
    )
    holidays = list(qs)

    # 2) text filter
    if search_val:
        holidays = [
            h for h in holidays
            if search_val in h['reason'].lower()
               or search_val in h['start_date'].isoformat()
               or search_val in h['end_date'].isoformat()
        ]

    # 3) year/month filter (Jalali)
    if filter_year and filter_mon:
        fy = int(filter_year)
        fm = int(filter_mon)

        def in_month(h):
            # convert Gregorian → Jalali
            j = jdatetime.date.fromgregorian(date=h['start_date'])
            return j.year == fy and j.month == fm

        holidays = [h for h in holidays if in_month(h)]

    total = len(holidays)

    # 4) sort
    key_map = {
        'description': 'reason',
        'start_date': 'start_date',
        'end_date': 'end_date',
        'days': 'days',
    }
    sk = key_map.get(order_by, 'start_date')
    # holidays.sort(key=lambda h: h[sk], reverse=(order_dir == 'desc'))
    holidays.sort(key=lambda h: h[sk], reverse=True)

    # 5) paginate
    page_obj = Paginator(holidays, page_size).get_page(page)

    # 6) build payload (convert back to YYYY/MM/DD)
    data = []
    for h in page_obj:
        js = jdatetime.date.fromgregorian(date=h['start_date']).strftime('%Y/%m/%d')
        je = jdatetime.date.fromgregorian(date=h['end_date']).strftime('%Y/%m/%d')
        data.append({
            'id': f"{h['start_date']}|{h['end_date']}",
            'description': h['reason'],
            'days': str(int(h['days'])),
            'start_date': js,
            'end_date': je,
        })

    return JsonResponse({
        'recordsTotal': total,
        'recordsFiltered': total,
        'data': data,
    })


@login_required(login_url='login')
@permission_required('core.add_public_holiday', raise_exception=True)
def add_public_holiday(request):
    old = {}
    if request.method == 'POST':
        old = request.POST.copy()
        sd_raw = request.POST.get('start_date', '').strip()  # e.g. "1404/02/07"
        ed_raw = request.POST.get('end_date', '').strip()
        desc = request.POST.get('description', '').strip()

        # — parse Jalali and convert to Gregorian —
        try:
            # split on slash
            sy, sm, sd = map(int, sd_raw.split('/'))
            ey, em, ed = map(int, ed_raw.split('/'))

            # convert to Gregorian date
            start_j = jdatetime.date(sy, sm, sd)
            end_j = jdatetime.date(ey, em, ed)
            sd_greg = start_j.togregorian()
            ed_greg = end_j.togregorian()

            if ed_greg < sd_greg:
                raise ValueError(_("End date must be on or after start date."))
        except Exception as e:
            messages.error(request, str(e))
            return render(request, 'attendance/add_public_holiday.html', {'old': old})

        # — count days excluding Fridays —
        days = (ed_greg - sd_greg).days + 1

        # — bulk-create one approved holiday per active employee —
        emps = Employee.objects.filter(is_archive=False)
        vacations = []
        now = timezone.now()
        for emp in emps:
            vacations.append(EmployeeVacation(
                employee=emp,
                type=EmployeeVacation.VacationType.GENERAL_HOLIDAY,
                start_date=sd_greg,
                end_date=ed_greg,
                days_requested=days,
                reason=desc,
                status=EmployeeVacation.Status.APPROVED,
                requested_at=now,
                processed_by=request.user,
                processed_at=now,
            ))

        with transaction.atomic():
            EmployeeVacation.objects.bulk_create(vacations)
            # ——— NEW: broadcast one public notification ———
            # convert back to Jalali strings once
            j_start = jdatetime.date.fromgregorian(date=sd_greg)
            j_end = jdatetime.date.fromgregorian(date=ed_greg)
            jalali_start = f"{j_start.year}-{j_start.month:02d}-{j_start.day:02d}"
            jalali_end = f"{j_end.year}-{j_end.month:02d}-{j_end.day:02d}"

            notify_send(
                actor=request.user,
                verb=_("public holiday added"),
                level="info",
                description=_("A public holiday has been scheduled from {start} to {end}. Reason: {reason}").format(start=jalali_start, end=jalali_end, reason=desc),
                public=True,  # this will send to all active users
            )
            # ————————————————————————————————

        messages.success(
            request,
            _("Public holiday added for %(count)d employees.") % {'count': len(vacations)}
        )
        return redirect('public_holidays')

    return render(request, 'attendance/add_public_holiday.html', {
        'old': old
    })


@login_required(login_url='login')
@permission_required('core.delete_public_holiday', raise_exception=True)
@csrf_exempt
def delete_public_holiday(request):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        comp_id = request.POST.get('id', '')  # e.g. "1404/02/07|1404/02/08"
        description = request.POST.get('description', '').strip()

        # split into the two Jalali strings
        try:
            jal_start, jal_end = comp_id.split('|')
        except ValueError:
            return JsonResponse({'success': False, 'error': _("Invalid holiday ID")}, status=400)

        # parse Jalali → togregorian()
        try:
            y1, m1, d1 = map(int, jal_start.split('/'))
            y2, m2, d2 = map(int, jal_end.split('/'))
            g_start = jdatetime.date(y1, m1, d1).togregorian()
            g_end = jdatetime.date(y2, m2, d2).togregorian()
        except Exception:
            return JsonResponse({'success': False, 'error': _("Invalid Jalali date format")}, status=400)

        # delete all matching GENERAL_HOLIDAY entries with the same start/end & reason
        deleted, details = EmployeeVacation.objects.filter(
            type=EmployeeVacation.VacationType.GENERAL_HOLIDAY,
            start_date=g_start,
            end_date=g_end,
            reason=description,
        ).delete()

        if deleted:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({
                'success': False,
                'error': _("No matching holiday found to delete.")
            }, status=404)

    return JsonResponse({'success': False, 'error': _("Invalid request")}, status=400)


@login_required(login_url='login')
@permission_required('core.view_employee_leave_list', raise_exception=True)
def employee_leave(request):
    """
    Render the Employee Leave page with year/month filters.
    """
    today = date.today()
    jtoday = jdatetime.date.fromgregorian(date=today)

    years = list(range(MIN_YEAR, jtoday.year + 2))[::-1]
    months = PERSIAN_MONTHS  # e.g. ['Hamal','Sawr',...]

    return render(request, "attendance/employee_leaves.html", {
        "years": years,
        "months": list(enumerate(months, start=1)),
        "current_year": jtoday.year,
        "current_month": jtoday.month,
        'is_admin_user': request.user.account_type != User.ACCOUNT_TYPE_EMPLOYEE,
    })


@login_required(login_url='login')
@permission_required('core.view_employee_leave_list', raise_exception=True)
def fetch_employee_leaves(request):
    """
    AJAX endpoint for DataTables: return EmployeeVacation rows (except GENERAL_HOLIDAY),
    filtered / sorted / paginated, and converted to Jalali dates for display.

    - normal employees see only their own requests
    - HODs see their own plus anyone in their department
    - all others (e.g. admin) see everyone
    """
    if request.method != 'POST':
        return JsonResponse({'error': _("Invalid request method.")}, status=400)

    user = request.user
    profile = getattr(user, 'employee_profile', None)
    is_emp = (user.account_type == User.ACCOUNT_TYPE_EMPLOYEE)
    is_hod = (is_emp and profile and profile.is_head_of_dep)

    # ─── DataTables parameters ───
    page = int(request.POST.get('page', 1))
    page_size = int(request.POST.get('page_size', 10))
    search_val = request.POST.get('search_value', '').strip().lower()
    order_by = request.POST.get('order_by', 'requested_at')
    order_dir = request.POST.get('order_dir', 'desc')
    filter_year = request.POST.get('filter_year')
    filter_month = request.POST.get('filter_month')
    reverse = (order_dir == 'desc')

    # ─── Base queryset ───
    qs = (
        EmployeeVacation.objects
        .exclude(type=EmployeeVacation.VacationType.GENERAL_HOLIDAY)
        .select_related('employee__user', 'processed_by', 'employee__department')
    )

    # ─── 1) Role-based filtering ───
    if is_emp:
        if is_hod:
            # include their own plus those in their department
            qs = qs.filter(
                Q(employee__user=user) |
                Q(employee__department=profile.department)
            )
        else:
            qs = qs.filter(employee__user=user)

    # materialize for in-Python search / sort
    leaves = list(qs)

    # ─── 2) Text search ───
    if search_val:
        def match(v):
            emp_id = str(v.employee.employee_id or '').lower()
            full_name = f"{v.employee.user.first_name} {v.employee.user.last_name}".lower()
            return (
                    search_val in emp_id or
                    search_val in full_name or
                    search_val in v.get_type_display().lower() or
                    search_val in v.start_date.isoformat() or
                    search_val in v.end_date.isoformat() or
                    search_val in (v.reason or '').lower()
            )

        leaves = [v for v in leaves if match(v)]

    # ─── 3) Year/month filter ───
    if filter_year and filter_month:
        fy, fm = int(filter_year), int(filter_month)

        def in_month(v):
            j = jdatetime.date.fromgregorian(date=v.start_date)
            return j.year == fy and j.month == fm

        leaves = [v for v in leaves if in_month(v)]

    total = len(leaves)

    # ─── 4) Sort ───
    key_map = {
        'employee_id': 'employee.employee_id',
        'full_name': 'employee.user.last_name',
        'type': 'type',
        'days': 'days_requested',
        'start_date': 'start_date',
        'end_date': 'end_date',
        'requested_at': 'requested_at',
        'sup': 'processed_by.username',
        'status': 'status',
    }
    sort_key = key_map.get(order_by, 'start_date')

    def get_nested_attr(obj, path):
        for part in path.split('.'):
            obj = getattr(obj, part)
        return obj

    leaves.sort(key=lambda v: get_nested_attr(v, sort_key), reverse=reverse)

    # ─── 5) Paginate ───
    page_obj = Paginator(leaves, page_size).get_page(page)

    # ─── 6) Build JSON rows ───
    default_photo = static('assets/images/user/default_profile_m.jpg')
    data = []
    for v in page_obj:
        eu = v.employee.user
        sup = v.processed_by
        sup_display = (
            f"{sup.first_name} {sup.last_name} ({sup.username})"
            if sup else ''
        )

        data.append({
            'id': v.id,
            'employee_id': v.employee.employee_id,
            'full_name': f"{eu.first_name} {eu.last_name}",
            'photo': eu.profile_photo.url if eu.profile_photo else default_photo,
            'type': v.get_type_display(),
            'days': str(int(v.days_requested)),
            'start_date': jdatetime.date.fromgregorian(date=v.start_date).strftime('%Y/%m/%d'),
            'end_date': jdatetime.date.fromgregorian(date=v.end_date).strftime('%Y/%m/%d'),
            'sup': sup_display,
            'status': v.status,
            'requested_at': v.requested_at.isoformat(),
        })

    return JsonResponse({
        'recordsTotal': total,
        'recordsFiltered': total,
        'data': data,
    })


@login_required(login_url='login')
@permission_required('core.add_employee_leave', raise_exception=True)
def add_employee_leave(request):
    """
    Form for an employee to request a new leave.
    """
    all_types = EmployeeVacation.VacationType.choices
    types = [
        (code, label)
        for code, label in all_types
        if code != EmployeeVacation.VacationType.GENERAL_HOLIDAY
    ]
    user = request.user
    is_employee = (user.account_type == User.ACCOUNT_TYPE_EMPLOYEE)

    # Base queryset of **all** active employees
    qs = Employee.objects.filter(is_archive=False).order_by('employee_id')

    # If this is a pure “employee” account, only let them pick themselves:
    if is_employee:
        qs = qs.filter(user=user)
        types = [
            (code, label)
            for code, label in types
            if code != EmployeeVacation.VacationType.CONSIDERATIONS
        ]

    employees = qs
    old = {}

    if request.method == 'POST':
        old = request.POST.copy()
        emp_id = request.POST.get('employee')
        vtype = request.POST.get('type')
        sd_raw = request.POST.get('start_date', '').strip()
        ed_raw = request.POST.get('end_date', '').strip()
        reason = request.POST.get('reason', '').strip()
        attach = request.FILES.get('attachment')

        errors = []

        # pull employee
        emp = Employee.objects.filter(employee_id=emp_id).first()
        if not emp:
            errors.append(_("Please select a valid employee."))

        # validate type
        if vtype not in dict(types):
            errors.append(_("Please select a valid leave type."))

        # parse Jalali → Gregorian
        try:
            sy, sm, sd = map(int, sd_raw.split('/'))
            ey, em_, ed = map(int, ed_raw.split('/'))
            jstart = jdatetime.date(sy, sm, sd)
            jend = jdatetime.date(ey, em_, ed)
            sd_g = jstart.togregorian()
            ed_g = jend.togregorian()
            if ed_g < sd_g:
                errors.append(_("End date must be on or after start date."))
        except Exception:
            errors.append(_("Please enter valid Jalali dates (YYYY/MM/DD)."))

        # compute days (excl Fridays)
        days = 0
        if not errors:
            d = sd_g
            while d <= ed_g:
                if d.weekday() != 4:
                    days += 1
                d += timedelta(days=1)

        # enforce annual limit
        if not errors and vtype in LEAVE_LIMITS and LEAVE_LIMITS[vtype] > 0:
            year = jstart.year
            # jalali-year range → gregorian bounds
            first_g = jdatetime.date(year, 1, 1).togregorian()
            last_g = jdatetime.date(year, 12, 29).togregorian()
            used = EmployeeVacation.objects.filter(
                employee=emp,
                type=vtype,
                start_date__gte=first_g,
                start_date__lte=last_g
            ).exclude(status=EmployeeVacation.Status.REJECTED).aggregate(total=Sum('days_requested'))['total'] or 0
            limit = LEAVE_LIMITS[vtype]
            if used + days > limit:
                errors.append(
                    _("You have already taken %(used)d of %(limit)d days for %(type)s this year.") % {
                        'used': used, 'limit': limit,
                        'type': dict(types)[vtype]
                    }
                )

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            # create the leave request
            with transaction.atomic():
                # find the head of this employee's department (if any)
                head_emp = Employee.objects.filter(
                    department=emp.department,
                    is_head_of_dep=True
                ).first()
                head_user = head_emp.user if head_emp else None

                lv = EmployeeVacation.objects.create(
                    employee=emp,
                    type=vtype,
                    start_date=sd_g,
                    end_date=ed_g,
                    days_requested=days,
                    reason=reason,
                    attachment=attach,
                    status=EmployeeVacation.Status.PENDING,
                    requested_at=timezone.now(),
                    processed_by=head_user,  # ← set to dept-head's User
                )

                # ————— NEW: send notification to the head —————
                if head_user:
                    # convert Gregorian back to Jalali strings
                    j_start = jdatetime.date.fromgregorian(date=sd_g)
                    j_end = jdatetime.date.fromgregorian(date=ed_g)
                    jalali_start = f"{j_start.year}/{j_start.month:02d}/{j_start.day:02d}"
                    jalali_end = f"{j_end.year}/{j_end.month:02d}/{j_end.day:02d}"

                    notify_send(
                        actor=request.user,
                        recipient=head_user,
                        verb=_("requested employee leave"),
                        action_object=lv,
                        target=lv,
                        level="info",
                        description=_(
                            "{user} requested a leave from {start} to {end}. Reason: {reason}"
                        ).format(
                            user=request.user.get_full_name(),
                            start=jalali_start,
                            end=jalali_end,
                            reason=reason or _("(no reason provided)")
                        ),
                        public=False,
                    )
                # ————————————————————————————————

            messages.success(request, _("Leave requested successfully."))
            return redirect('employee_leave')

    return render(request, 'attendance/add_employee_leave.html', {
        'types': types,
        'employees': employees,
        'old': old,
        'is_employee': is_employee,
    })


@login_required(login_url='login')
@permission_required('core.delete_employee_leave', raise_exception=True)
@csrf_exempt
def delete_employee_leave(request):
    """
    Deletes a single EmployeeVacation entry by ID.
    - Admins can delete any leave.
    - Non-admins may only delete their own leave requests, and only if not approved.
    """
    if request.method != 'POST' or request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': _("Invalid request.")}, status=400)

    vid = request.POST.get('id')
    vac = get_object_or_404(EmployeeVacation, pk=vid)

    user = request.user

    # Admins can delete any leave
    if user.account_type == User.ACCOUNT_TYPE_NORMAL:
        vac.delete()
        return JsonResponse({'success': True})

    # Non-admin users cannot delete approved leave
    if vac.status == EmployeeVacation.Status.APPROVED:
        return JsonResponse({
            'success': False,
            'error': _("Cannot delete an approved leave.")
        }, status=400)

    # Non-admins can only delete their own leave requests
    if user.account_type == User.ACCOUNT_TYPE_EMPLOYEE:
        if vac.employee.user != user:
            return JsonResponse({
                'success': False,
                'error': _("You may only delete your own leave requests.")
            }, status=403)

    # Passed all checks → delete
    vac.delete()
    return JsonResponse({'success': True})

@login_required(login_url='login')
@permission_required('core.view_employee_leave_details', raise_exception=True)
def get_employee_leave(request, leave_id):
    # Only serve AJAX requests
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    # Fetch or 404
    leave = get_object_or_404(
        EmployeeVacation.objects
        .select_related('employee__user', 'processed_by'),
        pk=leave_id
    )
    user = request.user

    # Convert Gregorian → Jalali strings
    js = jdatetime.date.fromgregorian(date=leave.start_date).strftime('%Y/%m/%d')
    je = jdatetime.date.fromgregorian(date=leave.end_date).strftime('%Y/%m/%d')

    # Convert processed_at datetime to Jalali (date + time)
    requested_j = jalali_datetime_str(leave.requested_at)
    processed_j = jalali_datetime_str(leave.processed_at) if leave.processed_at else ''

    # only allow confirm if user has the perm, it's pending, and it's not their own request
    can_confirm = (
            user.has_perm('core.confirm_employee_leave')
            and leave.status == EmployeeVacation.Status.PENDING
            and leave.employee.user != user
    )

    sup = leave.processed_by
    sup_display = (
        f"{sup.first_name} {sup.last_name} ({sup.username})"
        if sup else ''
    )

    data = {
        'full_name': f"{leave.employee.user.first_name} {leave.employee.user.last_name}",
        'employee_id': leave.employee.employee_id,
        'type': leave.get_type_display(),
        'days': str(int(leave.days_requested)),
        'start_date': js,
        'end_date': je,
        'reason': leave.reason or '',
        'attachment': leave.attachment.url if leave.attachment else '',
        'supervisor': sup_display,
        'status_label': leave.get_status_display(),
        'status_code': leave.status,
        'requested_at': requested_j,
        'processed_at': processed_j,
        'can_confirm': can_confirm,
    }
    return JsonResponse(data)


@login_required(login_url='login')
@permission_required('core.confirm_employee_leave', raise_exception=True)
@csrf_exempt
def update_employee_leave_status(request):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        vid = request.POST.get('id')
        status = request.POST.get('status')  # 'A' or 'R'
        try:
            lv = EmployeeVacation.objects.get(pk=vid)
            lv.status = status
            lv.processed_by = request.user
            lv.processed_at = timezone.now()
            lv.save()

            # ——— send notification back to the employee ———
            emp_user = lv.employee.user

            # convert Gregorian back to Jalali strings
            try:
                j_start = jdatetime.date.fromgregorian(date=lv.start_date)
                j_end = jdatetime.date.fromgregorian(date=lv.end_date)
                jalali_start = f"{j_start.year}/{j_start.month:02d}/{j_start.day:02d}"
                jalali_end = f"{j_end.year}/{j_end.month:02d}/{j_end.day:02d}"
            except Exception:
                # fallback to ISO if conversion fails
                jalali_start = lv.start_date.isoformat()
                jalali_end = lv.end_date.isoformat()

            if status == EmployeeVacation.Status.APPROVED:
                notif_verb = _("leave request approved")
                notif_level = "success"
                notif_desc = _("Your leave from {start} to {end} has been approved.").format(start=jalali_start, end=jalali_end)
            else:
                notif_verb = _("leave request rejected")
                notif_level = "error"
                notif_desc = _("Your leave from {start} to {end} has been rejected.").format(start=jalali_start, end=jalali_end)

            notify_send(
                actor=request.user,
                recipient=emp_user,
                verb=notif_verb,
                action_object=lv,
                target=lv,
                level=notif_level,
                description=notif_desc,
                public=False,
            )
            # ————————————————————————————————

            return JsonResponse({
                'success': True,
                'status_label': lv.get_status_display(),
                'status_code': lv.status,
            })
        except EmployeeVacation.DoesNotExist:
            return JsonResponse({'success': False, 'error': _("Leave not found")}, status=404)
    return JsonResponse({'success': False, 'error': _("Invalid request")}, status=400)


@login_required(login_url='login')
@permission_required('core.view_daily_leave_list', raise_exception=True)
def daily_leave(request):
    today = date.today()
    jtoday = jdatetime.date.fromgregorian(date=today)
    years = list(range(MIN_YEAR, jtoday.year + 2))[::-1]
    months = list(enumerate(PERSIAN_MONTHS, start=1))

    return render(request, "attendance/daily_leaves.html", {
        "years": years,
        "months": months,
        "current_year": jtoday.year,
        "current_month": jtoday.month,
        'is_admin_user': request.user.account_type != User.ACCOUNT_TYPE_EMPLOYEE,
    })


@login_required(login_url='login')
@permission_required('core.view_daily_leave_list', raise_exception=True)
def fetch_daily_leaves(request):
    if request.method != 'POST':
        return JsonResponse({'error': _("Invalid request method.")}, status=400)

    user = request.user
    profile = getattr(user, 'employee_profile', None)
    is_emp = (user.account_type == User.ACCOUNT_TYPE_EMPLOYEE)
    is_hod = (is_emp and profile and profile.is_head_of_dep)

    # DataTables inputs…
    page = int(request.POST['page'])
    page_size = int(request.POST['page_size'])
    search_val = request.POST.get('search_value', '').strip().lower()
    order_by = request.POST.get('order_by', 'requested_at')  # ← default to requested_at
    order_dir = request.POST.get('order_dir', 'desc')  # ← descending
    reverse = (order_dir == 'desc')
    filter_year = request.POST.get('filter_year')
    filter_mon = request.POST.get('filter_month')

    qs = DailyLeave.objects.select_related('employee__user', 'head_of_department')

    # ─── 1) Role-based filtering ───────────────────────────
    if is_emp:
        if is_hod:
            # their own + any in their department
            qs = qs.filter(
                Q(employee__user=user) |
                Q(employee__department=profile.department)
            )
        else:
            # only their own
            qs = qs.filter(employee__user=user)

    leaves = list(qs)

    # ─── 2) Search ─────────────────────────────────────────
    if search_val:
        def match(dl):
            empid = str(dl.employee.employee_id).lower()
            full = f"{dl.employee.user.first_name} {dl.employee.user.last_name}".lower()
            lt = dl.get_leave_type_display().lower()
            dt = dl.date.isoformat()
            reason = (dl.reason or '').lower()
            return (search_val in empid
                    or search_val in full
                    or search_val in lt
                    or search_val in dt
                    or search_val in reason)

        leaves = [dl for dl in leaves if match(dl)]

    # ─── 3) Year/Month Filter ──────────────────────────────
    if filter_year and filter_mon:
        fy, fm = int(filter_year), int(filter_mon)

        def in_month(dl):
            j = jdatetime.date.fromgregorian(date=dl.date)
            return j.year == fy and j.month == fm

        leaves = [dl for dl in leaves if dl.date and in_month(dl)]

    total = len(leaves)

    # ─── 4) Sort ───────────────────────────────────────────
    key_map = {
        'employee_id': 'employee.employee_id',
        'full_name': 'employee.user.last_name',
        'date': 'date',
        'leave_type': 'leave_type',
        'status': 'status',
        'requested_at': 'requested_at',
    }
    sort_key = key_map.get(order_by, 'requested_at')

    def get_attr(o, path):
        for part in path.split('.'):
            o = getattr(o, part)
        return o or ''

    leaves.sort(key=lambda dl: get_attr(dl, sort_key), reverse=reverse)

    # ─── 5) Paginate ───────────────────────────────────────
    page_obj = Paginator(leaves, page_size).get_page(page)

    # ─── 6) Build JSON ────────────────────────────────────
    default_photo = static('assets/images/user/default_profile_m.jpg')
    data = []
    for dl in page_obj:
        u = dl.employee.user
        employee_pk = dl.employee.id
        full = f"{u.first_name} {u.last_name}"
        photo = u.profile_photo.url if getattr(u, 'profile_photo', None) else default_photo
        head = dl.head_of_department.username if dl.head_of_department else ''

        sup = dl.head_of_department
        sup_display = (
            f"{sup.first_name} {sup.last_name} ({sup.username})"
            if sup else ''
        )

        req_jalali = jalali_datetime_str(dl.requested_at)

        raw_reason = dl.reason or ''

        # 2) truncate to 200 chars + “…” if it’s too long
        if len(raw_reason) > 50:
            display_reason = raw_reason[:50] + '...'
        else:
            display_reason = raw_reason

        data.append({
            'id': dl.id,
            'employee_pk': employee_pk,
            'employee_id': dl.employee.employee_id,
            'full_name': full,
            'photo': photo,
            'date': jdatetime.date.fromgregorian(date=dl.date).strftime('%Y/%m/%d') if dl.date else '',
            'leave_type': dl.get_leave_type_display(),
            'reason': display_reason,
            'head': sup_display,
            'status': dl.status,
            'requested_at': req_jalali,
        })

    return JsonResponse({
        'recordsTotal': total,
        'recordsFiltered': total,
        'data': data,
    })


@login_required(login_url='login')
@permission_required('core.view_daily_leave_details', raise_exception=True)
def get_daily_leave(request, leave_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid'}, status=400)

    l = get_object_or_404(
        DailyLeave.objects
        .select_related('employee__user', 'head_of_department'),
        pk=leave_id
    )

    # Format the requested date as Jalali
    jdate_str = jdatetime.date.fromgregorian(date=l.date).strftime('%Y/%m/%d')

    # Convert the datetimes into Jalali datetime strings
    requested_j = jalali_datetime_str(l.requested_at)
    processed_j = jalali_datetime_str(l.processed_at) if l.processed_at else ''

    user = request.user
    # only allow confirm if user has the perm, it's pending, and it's not their own request
    can_confirm = (
            user.has_perm('core.confirm_daily_leave')
            and l.status == EmployeeVacation.Status.PENDING
            and l.employee.user != user
    )

    return JsonResponse({
        'full_name': f"{l.employee.user.first_name} {l.employee.user.last_name}",
        'employee_id': l.employee.employee_id,
        'date': jdate_str,
        'leave_type': l.get_leave_type_display(),
        'reason': l.reason or '',
        'head': l.head_of_department.get_full_name()
        if l.head_of_department else '',
        'requested_at': requested_j,
        'processed_at': processed_j,
        'status_label': l.get_status_display(),
        'status_code': l.status,
        'can_confirm': can_confirm,
    })


@login_required(login_url='login')
@permission_required('core.confirm_daily_leave', raise_exception=True)
def update_daily_leave_status(request):
    if request.method != 'POST' or request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request.'}, status=400)

    lid = request.POST.get('id')
    new_st = request.POST.get('status')
    dl = get_object_or_404(DailyLeave, pk=lid)

    # Only wrap in a transaction if we're going to create logs and update leave
    with transaction.atomic():
        # If approving, we must successfully create logs first
        if new_st == DailyLeave.Status.ACCEPTED:
            emp = dl.employee
            leave = dl.leave_type  # one of 'IN','OUT','BOTH'

            # Convert the leave date (a Python date) to Jalali for schedule lookup
            try:
                jdate = jdatetime.date.fromgregorian(date=dl.date)
            except Exception:
                return JsonResponse({'error': 'Invalid leave date.'}, status=400)

            dow_code = PY_TO_SS_DOW_GREGORIAN.get(dl.date.weekday())
            if dow_code is None:
                return JsonResponse({'error': 'Could not determine day of week.'}, status=400)

            # Find the active schedule for this shift / year / month / weekday
            sched = ShiftSchedule.objects.filter(
                shift=emp.shift,
                year=jdate.year,
                month=jdate.month,
                day_of_week=dow_code,
                is_active=True
            ).first()

            if not sched:
                return JsonResponse({
                    'error': "No active shift schedule for "
                             f"{jdate.year}/{jdate.month}/{jdate.day}."
                }, status=400)

            # Helper to insert a log
            def make_log(log_type, rec_dt):
                AttendanceLog.objects.create(
                    employee=emp,
                    device=None,
                    timestamp=rec_dt,
                    log_type=log_type,
                    verification_type=AttendanceLog.VerificationType.MANUAL
                )

            # Build the two possible timestamps
            # Clock-in
            if leave in (DailyLeave.LeaveType.CLOCK_IN, DailyLeave.LeaveType.CLOCK_IN_OUT):
                if not sched.in_start_time:
                    return JsonResponse({'error': 'Shift schedule missing clock-in start time.'}, status=400)
                t_in = datetime.combine(dl.date, sched.in_start_time)
                make_log(AttendanceLog.LogType.CLOCK_IN, t_in)

            # Clock-out with overnight handling
            if leave in (DailyLeave.LeaveType.CLOCK_OUT, DailyLeave.LeaveType.CLOCK_IN_OUT):
                if not sched.out_start_time:
                    return JsonResponse({'error': 'Shift schedule missing clock-out start time.'}, status=400)

                # if out_time ≤ in_time → it’s actually on the next day
                if sched.in_start_time and sched.out_start_time <= sched.in_start_time:
                    out_date = dl.date + timedelta(days=1)
                else:
                    out_date = dl.date

                t_out = datetime.combine(out_date, sched.out_start_time)
                make_log(AttendanceLog.LogType.CLOCK_OUT, t_out)

        # At this point, either we're rejecting (no logs) or logs succeeded—so update the leave
        dl.status = new_st
        dl.head_of_department = request.user
        dl.processed_at = timezone.now()
        dl.save()

        # ——— send notification to the employee ———
        emp_user = dl.employee.user
        try:
            j_date = jdatetime.date.fromgregorian(date=dl.date)
            jalali_str = f"{j_date.year}/{j_date.month:02d}/{j_date.day:02d}"
        except:
            jalali_str = dl.date.isoformat()

        if new_st == DailyLeave.Status.ACCEPTED:
            notif_verb = _("daily leave request approved")
            notif_level = "success"
            notif_desc = _("Your daily leave on {date} has been approved.").format(date=jalali_str)
        else:
            notif_verb = _("daily leave request rejected")
            notif_level = "error"
            notif_desc = _("Your daily leave on {date} has been rejected.").format(date=jalali_str)

        notify_send(
            actor=request.user,
            recipient=emp_user,
            verb=notif_verb,
            action_object=dl,
            target=dl,
            level=notif_level,
            description=notif_desc,
            public=False,
        )

    return JsonResponse({'success': True})


@login_required(login_url='login')
@permission_required('core.add_daily_leave', raise_exception=True)
def add_daily_leave(request):
    leave_types = DailyLeave.LeaveType.choices
    user = request.user
    is_employee = (user.account_type == User.ACCOUNT_TYPE_EMPLOYEE)
    qs = Employee.objects.filter(is_archive=False)
    if is_employee:
        # employees only see themselves
        qs = qs.filter(user=user)

    employees = qs
    old = {}

    if request.method == 'POST':
        old = request.POST.copy()
        emp_id = request.POST['employee']
        dt_raw = request.POST['date'].strip()
        lt = request.POST['leave_type']
        reason = request.POST.get('reason', '').strip()

        errors = []
        emp = Employee.objects.filter(employee_id=emp_id).first()
        if not emp:
            errors.append(_("Select a valid employee."))

        # parse date
        try:
            y, m, d = map(int, dt_raw.split('/'))
            date_g = jdatetime.date(y, m, d).togregorian()
        except:
            errors.append(_("Enter a valid date (YYYY/MM/DD)."))

        if lt not in dict(leave_types):
            errors.append(_("Select a valid leave type."))

        if errors:
            for e in errors: messages.error(request, e)
        else:
            head_emp = Employee.objects.filter(
                department=emp.department,
                is_head_of_dep=True
            ).first()
            head_user = head_emp.user if head_emp else None

            leave = DailyLeave.objects.create(
                employee=emp,
                date=date_g,
                leave_type=lt,
                reason=reason,
                head_of_department=head_user,
                status=DailyLeave.Status.PENDING,
            )

            if head_user:
                # convert back to Jalali string
                j_date = jdatetime.date.fromgregorian(date=date_g)
                jalali_str = f"{j_date.year}-{j_date.month:02d}-{j_date.day:02d}"

                notify_send(
                    actor=request.user,
                    recipient=head_user,
                    verb=_("requested daily leave"),
                    action_object=leave,
                    target=leave,
                    level="info",
                    description=_(
                        "{user} requested a daily leave on {date}. Reason: {reason}"
                    ).format(
                        user=request.user.get_full_name(),
                        date=jalali_str,
                        reason=reason or _("(no reason provided)")
                    ),
                    public=False,
                )

            messages.success(request, _("Daily leave requested."))
            return redirect('daily_leave')

    return render(request, 'attendance/add_daily_leave.html', {
        'leave_types': leave_types,
        'employees': employees,
        'old': old,
        'is_employee': is_employee,
    })


@login_required(login_url='login')
@permission_required('core.delete_daily_leave', raise_exception=True)
@csrf_exempt
def delete_daily_leave(request):
    if request.method != 'POST' or request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': _("Invalid request.")}, status=400)

    dl = get_object_or_404(DailyLeave, pk=request.POST.get('id'))

    # Only pending
    if dl.status != DailyLeave.Status.PENDING:
        return JsonResponse({'success': False, 'error': _("Only pending requests can be deleted.")}, status=400)

    # Only self-delete for employees (even heads)
    if request.user.account_type == User.ACCOUNT_TYPE_EMPLOYEE:
        if dl.employee.user_id != request.user.id:
            return JsonResponse({'success': False, 'error': _("Not authorized to delete this.")}, status=403)

    dl.delete()
    return JsonResponse({'success': True})


@login_required(login_url='login')
@permission_required('core.view_make_absent', raise_exception=True)
def make_absent(request):
    # common context data for form
    employees = Employee.objects.filter(is_archive=False)
    leave_types = DailyLeave.LeaveType.choices
    days_range = range(1, 32)
    jnow = jdatetime.date.today()
    years = list(range(MIN_YEAR, jnow.year + 2))[::-1]
    months = list(enumerate(PERSIAN_MONTHS, start=1))

    if request.method == 'POST':
        emp_ids = request.POST.getlist('employee')
        year = request.POST.get('year')
        month = request.POST.get('month')
        days_selected = request.POST.getlist('days')
        absent_type = request.POST.get('leave_type')

        errors = []
        if not emp_ids:
            errors.append("You must select at least one employee.")
        if not year or not month:
            errors.append("Year and month are required.")
        if not days_selected:
            errors.append("You must select at least one day.")
        if not absent_type:
            errors.append("Absent Type is required.")

        # parse year/month
        try:
            jy, jm = int(year), int(month)
        except (TypeError, ValueError):
            errors.append("Invalid year or month.")

        # parse days
        days_int = []
        for d in days_selected:
            try:
                di = int(d)
                if 1 <= di <= 31:
                    days_int.append(di)
                else:
                    errors.append(f"Day {di} is out of range.")
            except ValueError:
                errors.append(f"Invalid day: {d}")

        # validate absent_type
        valid_types = {code for code, _ in leave_types}
        if absent_type not in valid_types:
            errors.append("Invalid Absent Type selected.")

        if errors:
            for msg in errors:
                messages.error(request, msg)
            return redirect('make_absent')

        removed = 0
        with transaction.atomic():
            for emp_id in emp_ids:
                emp = get_object_or_404(Employee, employee_id=emp_id, is_archive=False)
                for di in days_int:
                    # Convert Jalali → Gregorian date
                    try:
                        jdate = jdatetime.date(jy, jm, di)
                        gdate = jdate.togregorian()
                    except Exception:
                        messages.error(request, f"Invalid date {jy}-{jm}-{di}")
                        continue

                    # map weekday for schedule lookup
                    dow = PY_TO_SS_DOW_GREGORIAN.get(gdate.weekday())
                    sched = ShiftSchedule.objects.filter(
                        shift=emp.shift,
                        year=jdate.year,
                        month=jdate.month,
                        day_of_week=dow,
                        is_active=True
                    ).first()
                    if not sched:
                        messages.error(request, f"No schedule for {emp} on {gdate}.")
                        continue

                    # For IN logs
                    if absent_type in (DailyLeave.LeaveType.CLOCK_IN,
                                       DailyLeave.LeaveType.CLOCK_IN_OUT):
                        q = AttendanceLog.objects.filter(
                            employee=emp,
                            log_type=AttendanceLog.LogType.CLOCK_IN,
                            timestamp__date=gdate
                        )
                        count, details = q.delete()
                        removed += count

                    # For OUT logs
                    if absent_type in (DailyLeave.LeaveType.CLOCK_OUT,
                                       DailyLeave.LeaveType.CLOCK_IN_OUT):
                        # detect overnight: out_time ≤ in_time ⇒ next calendar day
                        if sched.in_start_time and sched.out_start_time <= sched.in_start_time:
                            out_date = gdate + timedelta(days=1)
                        else:
                            out_date = gdate

                        q = AttendanceLog.objects.filter(
                            employee=emp,
                            log_type=AttendanceLog.LogType.CLOCK_OUT,
                            timestamp__date=out_date
                        )
                        count, details = q.delete()
                        removed += count

        if removed:
            messages.success(
                request,
                _("Removed %(count)d attendance record%(plural)s.") % {
                    'count': removed,
                    'plural': _("s") if removed != 1 else ''
                }
            )
        else:
            messages.info(request, _("No matching attendance records were found to remove."))

        return redirect('make_absent')

    # GET: render same form
    return render(request, 'reports/make_absent_form.html', {
        'employees': employees,
        'leave_types': leave_types,
        'days_range': days_range,
        'years': years,
        'months': months,
        'old': {},
        # you might pass a flag so the template can adjust its title/action
        'is_absent': True,
    })


@login_required(login_url='login')
@permission_required('core.view_make_present', raise_exception=True)
def make_present(request):
    employees = Employee.objects.filter(is_archive=False)
    leave_types = DailyLeave.LeaveType.choices
    days_range = range(1, 32)

    jnow = jdatetime.date.today()
    years = list(range(MIN_YEAR, jnow.year + 2))[::-1]
    months = list(enumerate(PERSIAN_MONTHS, start=1))

    if request.method == 'POST':
        emp_ids = request.POST.getlist('employee')
        year = request.POST.get('year')
        month = request.POST.get('month')
        days_selected = request.POST.getlist('days')
        present_type = request.POST.get('leave_type')

        errors = []
        if not emp_ids:
            errors.append("You must select at least one employee.")
        if not year or not month:
            errors.append("Year and month are required.")
        if not days_selected:
            errors.append("You must select at least one day.")
        if not present_type:
            errors.append("Present Type is required.")

        try:
            jy, jm = int(year), int(month)
        except (TypeError, ValueError):
            errors.append("Invalid year or month.")

        days_int = []
        for d in days_selected:
            try:
                di = int(d)
                if 1 <= di <= 31:
                    days_int.append(di)
                else:
                    errors.append(f"Day {di} is out of range.")
            except ValueError:
                errors.append(f"Invalid day: {d}")

        valid_types = {code for code, _ in leave_types}
        if present_type not in valid_types:
            errors.append("Invalid Present Type selected.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('make_present')

        created = 0
        with transaction.atomic():
            for emp_id in emp_ids:
                emp = get_object_or_404(Employee, employee_id=emp_id, is_archive=False)

                for di in days_int:
                    # Convert Jalali → Gregorian
                    try:
                        jdate = jdatetime.date(jy, jm, di)
                        gdate = jdate.togregorian()
                    except Exception:
                        messages.error(request, f"Invalid date {jy}-{jm}-{di}")
                        continue

                    dow = PY_TO_SS_DOW_GREGORIAN.get(gdate.weekday())
                    if dow is None:
                        messages.error(request, f"Cannot map weekday for {gdate}.")
                        continue

                    sched = ShiftSchedule.objects.filter(
                        shift=emp.shift,
                        year=jdate.year,
                        month=jdate.month,
                        day_of_week=dow,
                        is_active=True
                    ).first()
                    if not sched:
                        messages.error(request, f"No schedule for {emp} on {gdate}.")
                        continue

                    def make_log(log_type, ts):
                        # skip duplicates
                        exists = AttendanceLog.objects.filter(
                            employee=emp,
                            log_type=log_type,
                            timestamp=ts
                        ).exists()
                        if not exists:
                            AttendanceLog.objects.create(
                                employee=emp,
                                device=None,
                                timestamp=ts,
                                log_type=log_type,
                                verification_type=AttendanceLog.VerificationType.MANUAL
                            )
                            return True
                        return False

                    # Clock-In
                    if present_type in (DailyLeave.LeaveType.CLOCK_IN,
                                        DailyLeave.LeaveType.CLOCK_IN_OUT):
                        if not sched.in_start_time:
                            messages.error(request, f"Missing clock-in start for {gdate}.")
                        else:
                            ts = datetime.combine(gdate, sched.in_start_time)
                            if make_log(AttendanceLog.LogType.CLOCK_IN, ts):
                                created += 1

                    # Clock-Out
                    if present_type in (DailyLeave.LeaveType.CLOCK_OUT,
                                        DailyLeave.LeaveType.CLOCK_IN_OUT):
                        if not sched.out_start_time:
                            messages.error(request, f"Missing clock-out start for {gdate}.")
                        else:
                            # detect overnight: if out_time ≤ in_time, it's on the next calendar day
                            if sched.in_start_time and sched.out_start_time <= sched.in_start_time:
                                out_date = gdate + timedelta(days=1)
                            else:
                                out_date = gdate

                            ts = datetime.combine(out_date, sched.out_start_time)
                            if make_log(AttendanceLog.LogType.CLOCK_OUT, ts):
                                created += 1

        if created:
            messages.success(
                request,
                _("Created %(count)d attendance log%(plural)s.") % {
                    'count': created,
                    'plural': '' if created == 1 else 's'
                }
            )
        else:
            messages.info(
                request,
                _("No new attendance logs were created (duplicates skipped).")
            )

        return redirect('make_present')

    # GET
    return render(request, 'reports/make_present_form.html', {
        'employees': employees,
        'leave_types': leave_types,
        'days_range': days_range,
        'years': years,
        'months': months,
        'old': {},
    })


# --------------------------- reports ----------------------------

@login_required(login_url='login')
@permission_required('core.check_attendance', raise_exception=True)
def check_attendance(request):
    user = request.user
    profile = getattr(user, 'employee_profile', None)
    is_employee = user.account_type == user.ACCOUNT_TYPE_EMPLOYEE
    can_view_dept = (
            profile
            and profile.is_head_of_dep
            and user.has_perm('core.view_daily_report_all_employee_by_hod')
    )

    # Base employees queryset
    qs = Employee.objects.filter(is_archive=False).order_by('employee_id')
    if is_employee:
        if can_view_dept:
            qs = qs.filter(department=profile.department)
        else:
            qs = qs.filter(user=user)

    # AJAX POST: return raw logs, no schedule logic
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        emp_id = request.POST.get('employee')
        date_str = request.POST.get('date')

        # parse Jalali date
        try:
            jy, jm, jd = map(int, date_str.split('/'))
            g_date = jdatetime.date(jy, jm, jd).togregorian()
        except:
            return JsonResponse({'error': _('Invalid date format')}, status=400)

        # filter by employee if provided
        employees = qs
        if emp_id:
            employees = employees.filter(employee_id=emp_id)

        # pick the employee instance
        employee = employees.first()
        if not employee:
            return JsonResponse({'error': _('Employee not found')}, status=404)

        # Query all logs on that date for that employee
        logs = AttendanceLog.objects.filter(
            employee=employee,
            timestamp__date=g_date
        ).order_by('timestamp')

        # Build rows directly from logs
        rows = []
        for lg in logs:
            vt = lg.verification_type
            # pick the right icon filename
            icon = None
            if vt == AttendanceLog.VerificationType.FINGERPRINT:
                icon = 'finger.png'
            elif vt == AttendanceLog.VerificationType.FACE:
                icon = 'face.png'
            elif vt == AttendanceLog.VerificationType.CARD:
                icon = 'card.jpg'
            # if AttendanceLog.device is a FK to a Device with .name
            device_name = lg.device.name if getattr(lg, 'device', None) else ''
            rows.append({
                'emp_id': employee.employee_id,
                'time': lg.timestamp.strftime('%I:%M:%S %p'),
                'device': device_name,
                'verification': getattr(vt, 'label', str(vt)),
                'icon': icon,
            })

        return JsonResponse({'rows': rows})

    # GET → render form
    return render(request, 'reports/check_attendance_form.html', {
        'employees': qs,
        'is_employee': is_employee,
        'can_view_dept': can_view_dept,
    })


@login_required(login_url='login')
@permission_required('core.view_daily_attendance', raise_exception=True)
def daily_attendance(request):
    """
    GET:   show the form.
    POST:  render a paginated, print-style report.
    """
    user = request.user
    profile = getattr(user, 'employee_profile', None)
    is_employee = user.account_type == user.ACCOUNT_TYPE_EMPLOYEE
    can_view_dept = (
            profile
            and profile.is_head_of_dep
            and user.has_perm('core.view_daily_report_all_employee_by_hod')
    )

    # Base employees queryset, sorted ASC by employee_id
    qs = Employee.objects.filter(is_archive=False).order_by('employee_id')
    if is_employee:
        if can_view_dept:
            qs = qs.filter(department=profile.department)
        else:
            qs = qs.filter(user=user)

    # qs = qs.filter(department=15) #its just for testing

    employees = qs

    old = {}

    if request.method == 'POST':
        old = request.POST.copy()
        # 1) Parse Jalali date
        ds = old.get('date', '').strip()
        try:
            jy, jm, jd = map(int, ds.split('/'))
            jdate = jdatetime.date(jy, jm, jd)
            g_date = jdate.togregorian()
        except Exception:
            return render(request, 'reports/daily_attendance_form.html', {
                'employees': employees,
                'old': old,
                'date_error': _("Invalid date format, use YYYY/MM/DD"),
                'is_employee': is_employee,
                'can_view_dept': can_view_dept,
            })

        # 3) Optional employee filter
        emp_id = old.get('employee')

        # Build the same sched_map you use in your helper
        jday = jdatetime.date.fromgregorian(date=g_date)
        ss_dow = PY_TO_SS_DOW_JALALI[jdate.weekday()]

        schedules = ShiftSchedule.objects.filter(
            year=jday.year,
            month=jday.month,
            day_of_week=ss_dow,
            is_active=True
        )
        sched_map = {sch.shift_id: sch for sch in schedules}

        # Which shift_ids your employees actually have…
        emp_shift_ids = set(employees.values_list('shift_id', flat=True))

        # …and which ones you fetched schedules for:
        scheduled_ids = set(sched_map)

        missing_ids = emp_shift_ids - scheduled_ids
        print(missing_ids)
        if missing_ids:
            missing_names = Shift.objects.filter(
                id__in=missing_ids
            ).values_list('name', flat=True)
            messages.warning(
                request,
                "این شیفت‌ها تقسیم اوقات ندارند: " + ", ".join(missing_names)
            )
            return redirect('daily_attendance')

        if emp_id and not is_employee:
            employees = employees.filter(employee_id=emp_id)
        # 4) Use helper for attendance
        attendance = get_daily_attendance(
            att_date=g_date,
            is_follow_schedule=True,
            has_emp_list=True,
            employee_qs=employees,
        )
        ci_rows = attendance['clock_in']['present']
        co_rows = attendance['clock_out']['present']
        # 5) Build placeholder dict
        real = {
            emp.id: {
                'emp_id': emp.employee_id,
                'first_name': emp.user.first_name,
                'last_name': emp.user.last_name,
                'father_name': getattr(emp, 'father_name', ''),
                'am': None,
                'pm': None,
                'vt': None,
                'device': None,
            } for emp in employees
        }
        # 6) Populate AM and PM
        for rec in ci_rows:
            entry = real[rec['employee_id']]
            entry['am'] = rec['timestamp']
            entry['vt'] = rec['verification_type']
            entry['device'] = rec['device_id']
        for rec in co_rows:
            entry = real[rec['employee_id']]
            entry['pm'] = rec['timestamp']
            entry['vt'] = rec['verification_type']
            entry['device'] = rec['device_id']

        # 7) Format and segregate absent
        def fmt_parts(dt):
            if not dt:
                return "غیر حاضر", ""
            # convert to Jalali date
            jd = jdatetime.date.fromgregorian(date=dt.date())
            date_str = jd.strftime("%Y-%m-%d")  # e.g. 1404-01-21
            time_str = dt.strftime("%I:%M:%S %p")  # e.g. 09:03:10 AM
            return date_str, time_str

        final = []
        for emp in employees:
            r = real[emp.id]
            vt = r['vt']
            icon = None
            if vt == AttendanceLog.VerificationType.FINGERPRINT:
                icon = 'finger.png'
            elif vt == AttendanceLog.VerificationType.FACE:
                icon = 'face.png'
            elif vt == AttendanceLog.VerificationType.CARD:
                icon = 'card.jpg'
            am_date, am_time = fmt_parts(r['am'])
            pm_date, pm_time = fmt_parts(r['pm'])
            final.append({
                'emp_id': r['emp_id'],
                'first_name': r['first_name'],
                'last_name': r['last_name'],
                'father_name': r['father_name'],
                'am_date': am_date,
                'am_time': am_time,
                'pm_date': pm_date,
                'pm_time': pm_time,
                'icon': icon,
            })
        # move fully absent to end
        present_list = [f for f in final if not (f['am_date'] == 'غیر حاضر' and f['pm_date'] == 'غیر حاضر')]
        absent_list = [f for f in final if (f['am_date'] == 'غیر حاضر' and f['pm_date'] == 'غیر حاضر')]
        final = present_list + absent_list

        # Collect attendance stats for summary
        total_am_present = sum(1 for r in final if r['am_date'] != "غیر حاضر")
        total_am_absent = sum(1 for r in final if r['am_date'] == "غیر حاضر")
        total_pm_present = sum(1 for r in final if r['pm_date'] != "غیر حاضر")
        total_pm_absent = sum(1 for r in final if r['pm_date'] == "غیر حاضر")
        total_both_present = sum(1 for r in final if r['am_date'] != "غیر حاضر" and r['pm_date'] != "غیر حاضر")
        total_any_absent = sum(1 for r in final if r['am_date'] == "غیر حاضر" or r['pm_date'] == "غیر حاضر")

        # 8) paginate by 15
        chunk_size = 15
        pages = [
            {'start': i, 'records': final[i:i + chunk_size]}
            for i in range(0, len(final), chunk_size)
        ]
        # 9) Jalali date string
        month_name = PERSIAN_MONTHS[jdate.month - 1]
        jdate_str = f"{jdate.day} – {_(month_name)} – {jdate.year}"

        return render(request, 'reports/daily_attendance_report.html', {
            'pages': pages,
            'jdate_str': jdate_str,
            'page_title': _("Daily Attendance Report"),
            'total_am_present': total_am_present,
            'total_am_absent': total_am_absent,
            'total_pm_present': total_pm_present,
            'total_pm_absent': total_pm_absent,
            'total_both_present': total_both_present,
            'total_any_absent': total_any_absent,
        })

    # GET
    return render(request, 'reports/daily_attendance_form.html', {
        'employees': employees,
        'old': old,
        'is_employee': is_employee,
        'can_view_dept': can_view_dept,
    })


@login_required(login_url='login')
@permission_required('core.view_monthly_attendance', raise_exception=True)
def monthly_attendance(request):
    user = request.user
    profile = getattr(user, 'employee_profile', None)
    is_employee = (user.account_type == user.ACCOUNT_TYPE_EMPLOYEE)
    can_view_dept = (
            is_employee and profile and profile.is_head_of_dep and
            user.has_perm('core.view_monthly_report_all_employee_by_hod')
    )

    # Base employees
    qs = Employee.objects.filter(is_archive=False)
    if is_employee:
        qs = qs.filter(
            department=profile.department if can_view_dept else None,
            user=None if can_view_dept else user
        )
    employees = qs.order_by('employee_id')

    departments = Department.objects.order_by('name')
    work_types = Employee.WORK_TYPE_CHOICES

    today_j = jdatetime.date.fromgregorian(date=date.today())
    years = list(range(MIN_YEAR, today_j.year + 2))[::-1]
    months = list(enumerate(PERSIAN_MONTHS, start=1))

    if request.method == 'POST':
        old = request.POST.copy()
        jy = int(old['year'])
        jm = int(old['month'])

        # 1) build your Gregorian window
        jstart = jdatetime.date(jy, jm, 1)
        jnext = jdatetime.date(jy + (jm // 12), (jm % 12) + 1, 1)
        gstart = jstart.togregorian()
        gend = jnext.togregorian() - timedelta(days=1)

        # 2) two‐case filter
        qs = Employee.objects.filter(
            Q(is_archive=False) | Q(is_archive=True, archive_date__isnull=False, archive_date__gte=gstart),
            created_at__date__lte=gend,
        )

        # Apply existing filters
        if is_employee:
            if can_view_dept:
                qs = qs.filter(department=profile.department)
            else:
                qs = qs.filter(user=user)

        # Additional filters from POST
        if (not is_employee or can_view_dept) and request.POST.get('employee'):
            qs = qs.filter(employee_id=request.POST['employee'])
        if not is_employee and request.POST.get('department'):
            qs = qs.filter(department_id=request.POST['department'])
        if (not is_employee or can_view_dept) and request.POST.get('work_type'):
            qs = qs.filter(work_type=request.POST['work_type'])

        employees = qs.order_by('employee_id')

        # page size
        try:
            page_size = max(int(old.get('page_size', 10)), 1)
        except ValueError:
            page_size = 10

        # get days & grid
        days, grid = get_monthly_attendance(
            year=jy, month=jm,
            is_follow_schedule=True,
            employee_qs=employees
        )

        dept_name = ''
        dept_id = old.get('department')
        if dept_id:
            dept = Department.objects.filter(id=dept_id).first()
            if dept:
                dept_name = dept.name

        work_type_name = ''
        if old.get('work_type') == Employee.CONTRACTOR:
            work_type_name = 'کارکنان حق الزحمه / باالمقطع'

        # add record numbers & paginate
        for idx, row in enumerate(grid, start=1):
            row['record_number'] = idx
        pages = [grid[i:i + page_size] for i in range(0, len(grid), page_size)]

        jdate_str = f"{jy} – {PERSIAN_MONTHS[jm - 1]}"
        return render(request, 'reports/monthly_attendance_report.html', {
            'page_title': _('Monthly Attendance'),
            'jdate_year': jy,
            'jdate_month': PERSIAN_MONTHS[jm - 1],
            'jdate_str': jdate_str,
            'department_name': dept_name,
            'work_type_name': work_type_name,
            'days': days,
            'pages': pages,
        })

    # GET
    old = {}
    return render(request, 'reports/monthly_attendance_form.html', {
        'employees': employees,
        'departments': departments,
        'work_types': work_types,
        'years': years,
        'months': months,
        'old': old,
        'is_employee': is_employee,
        'can_view_dept': can_view_dept,
    })


@login_required(login_url='login')
@permission_required('core.view_attendance_report', raise_exception=True)
def attendance_report(request):
    today_j = jdatetime.date.fromgregorian(date=date.today())
    years = list(range(MIN_YEAR, today_j.year + 2))[::-1]
    months = list(enumerate(PERSIAN_MONTHS, start=1))
    employees = Employee.objects.filter(is_archive=False).order_by('employee_id')
    departments = Department.objects.order_by('name')
    work_types = Employee.WORK_TYPE_CHOICES

    context = {
        'years': years,
        'months': months,
        'employees': employees,
        'departments': departments,
        'work_types': work_types,
        'old': request.POST if request.method == 'POST' else {},
    }

    if request.method == 'POST':
        # parse Jalali year/month from form
        jy = int(request.POST['year'])
        jm = int(request.POST['month'])

        # 1) build your Gregorian window
        jstart = jdatetime.date(jy, jm, 1)
        jnext = jdatetime.date(jy + (jm // 12), (jm % 12) + 1, 1)
        gstart = jstart.togregorian()
        gend = jnext.togregorian() - timedelta(days=1)

        # 2) two‐case filter
        # employees_qs = Employee.objects.filter(
        #     Q(
        #         # still active → include anytime after hire
        #         archive_date__isnull=True,
        #         created_at__date__lte=gend,
        #     ) | Q(
        #         # archived → include only while they overlapped this month
        #         archive_date__isnull=False,
        #         created_at__date__lte=gend,
        #         archive_date__gte=gstart,
        #     )
        # )
        employees_qs = Employee.objects.filter(
            Q(is_archive=False) | Q(is_archive=True, archive_date__isnull=False, archive_date__gte=gstart),
            created_at__date__lte=gend,
        )

        # apply optional filters
        if emp_id := request.POST.get('employee'):
            employees_qs = employees_qs.filter(id=emp_id)
        if dept := request.POST.get('department'):
            employees_qs = employees_qs.filter(department_id=dept)
        if wt := request.POST.get('work_type'):
            employees_qs = employees_qs.filter(work_type=wt)

        # compute the attendance summary
        summary = get_attendance_summary(
            year=jy,
            month=jm,
            is_follow_schedule=True,
            employee_qs=employees_qs,
        )

        dept_name = ''
        dept_id = request.POST.get('department')
        if dept_id:
            dept = Department.objects.filter(id=dept_id).first()
            if dept:
                dept_name = dept.name

        # paginate summary into pages of size N
        page_size = int(request.POST.get('page_size', 10))
        pages = [summary[i:i + page_size] for i in range(0, len(summary), page_size)]

        work_type_short_name = ''
        work_type_name = ''
        if wt == Employee.CONTRACTOR:
            work_type_short_name = 'بالمقطع'
            work_type_name = 'کارکنان حق الزحمه / باالمقطع'
        # add rendered context
        context.update({
            'page_title': _("Attendance Report"),
            'jdate_month': PERSIAN_MONTHS[jm - 1],
            'jdate_year': jy,
            'pages': pages,
            'department_name': dept_name,
            'work_type_short_name': work_type_short_name,
            'work_type_name': work_type_name,
            'page_size': page_size,
            'total_employees': len(summary),
        })
        return render(request, 'reports/attendance_report.html', context)

    # GET: display the form
    return render(request, 'reports/attendance_report_form.html', context)


@login_required(login_url='login')
@permission_required('core.view_employee_list_report', raise_exception=True)
def employee_report(request):
    # --- common form context ---
    all_emps = Employee.objects.filter(is_archive=False)
    departments = Department.objects.all()
    shifts = Shift.objects.filter(is_active=True)
    work_types = Employee.WORK_TYPE_CHOICES
    # Note: gender live on User; present for filtering
    gender_choices = [
        ('', _('Any')),
        ('M', _('Male')),
        ('F', _('Female')),
    ]
    status_choices = [
        ('', _('Any')),
        ('active', _('Active')),
        ('archived', _('Archived')),
    ]

    if request.method == 'POST':
        # 1) pull filters
        emp_ids = request.POST.getlist('employee')
        dept_ids = request.POST.getlist('department')
        shift_ids = request.POST.getlist('shift')
        gender = request.POST.get('gender')
        work_type = request.POST.get('work_type')
        status = request.POST.get('status')

        # 2) build base qs
        qs = Employee.objects.select_related('user', 'department', 'shift').all()
        if emp_ids:
            qs = qs.filter(employee_id__in=emp_ids)
        if dept_ids:
            qs = qs.filter(department_id__in=dept_ids)
        if shift_ids:
            qs = qs.filter(shift_id__in=shift_ids)
        if gender:
            qs = qs.filter(user__gender=gender)
        if work_type:
            qs = qs.filter(work_type=work_type)
        if status == 'active':
            qs = qs.filter(is_archive=False)
        elif status == 'archived':
            qs = qs.filter(is_archive=True)

        # 3) order & enumerate
        emps = list(qs.order_by('user__first_name', 'user__last_name'))
        if not emps:
            messages.warning(request, _("No employees found matching those filters."))
            return redirect('employee_report')

        numbered = [
            {'employee': emp, 'row_num': idx + 1}
            for idx, emp in enumerate(emps)
        ]

        # 4) paginate 15/pg
        page_size = int(request.POST.get('page_size', 12))
        pages = chunked(numbered, page_size)

        # 5) header
        today = date.today()
        jtoday = jdatetime.date.fromgregorian(date=today)
        jdate_str = f"{jtoday.year}-{jtoday.month}-{jtoday.day}"
        page_title = _("Employee Report")

        department_name = Department.objects.get(pk=dept_ids[0]).name
        work_type_name = dict(Employee.WORK_TYPE_CHOICES).get(work_type, '')

        return render(request, 'reports/employee_report.html', {
            'page_title': page_title,
            'jdate_str': jdate_str,
            'pages': pages,
            'department_name': department_name,
            'work_type_name': work_type_name,
            'page_size': page_size,
        })

    # GET → render the filter form
    return render(request, 'reports/employee_report_form.html', {
        'employees': all_emps,
        'departments': departments,
        'shifts': shifts,
        'gender_choices': gender_choices,
        'work_type_choices': work_types,
        'status_choices': status_choices,
        'old': {},  # no pre-selection on fresh GET
    })


@login_required(login_url='login')
@permission_required('core.view_permanent_absent_report', raise_exception=True)
def permanent_absent_report(request):
    all_emps = Employee.objects.filter(is_archive=False)
    departments = Department.objects.all()
    work_types = Employee.WORK_TYPE_CHOICES

    if request.method == 'POST':
        # 1) Filters + sort
        emp_ids = request.POST.getlist('employee')
        dept_id = request.POST.get('department')
        work_type = request.POST.get('work_type')
        page_size = int(request.POST.get('page_size', 12))

        qs = all_emps
        if emp_ids:
            qs = qs.filter(employee_id__in=emp_ids)
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        if work_type:
            qs = qs.filter(work_type=work_type)

        qs = qs.order_by('user__first_name')
        emps = list(qs)
        if not emps:
            messages.warning(request, _("No employees match those filters."))
            return redirect('permanent_absent_report')

        # 2) Fixed 1-year window
        today = date.today()
        start_date = today - timedelta(days=60)

        # 3) Bulk-fetch any log days
        log_entries = AttendanceLog.objects.filter(
            employee__in=emps,
            timestamp__date__range=(start_date, today)
        ).values_list('employee_id', 'timestamp__date').distinct()

        present_dates = defaultdict(set)
        for eid, d in log_entries:
            present_dates[eid].add(d)

        # 4) Bulk-fetch approved vacations
        vac_qs = EmployeeVacation.objects.filter(
            employee__in=emps,
            status=EmployeeVacation.Status.APPROVED,
            start_date__lte=today,
            end_date__gte=start_date
        ).values('employee_id', 'start_date', 'end_date')

        vacations = defaultdict(list)
        for e in vac_qs:
            eid = e['employee_id']
            s = max(e['start_date'], start_date)
            t = min(e['end_date'], today)
            vacations[eid].append((s, t))

        def on_vac(eid, d):
            return any(s <= d <= t for s, t in vacations.get(eid, ()))

        # 5) For each emp, find *all* ≥20-day runs, then pick the **last** one
        records = []
        for emp in emps:
            eid = emp.id
            seq_start = None
            d = start_date
            runs = []

            while d <= today:
                if d in present_dates[eid] or on_vac(eid, d):
                    # close a run if it was ongoing
                    if seq_start:
                        length = (d - seq_start).days
                        if length >= 20:
                            runs.append((seq_start, d - timedelta(days=1)))
                        seq_start = None
                else:
                    # mark start of run
                    if seq_start is None:
                        seq_start = d
                d += timedelta(days=1)

            # tail-run
            if seq_start:
                length = (today - seq_start).days + 1
                if length >= 20:
                    runs.append((seq_start, today))

            # if we have any runs, take only the *last* one
            if runs:
                start_run, end_run = runs[-1]
                days = (end_run - start_run).days + 1

                js = jdatetime.date.fromgregorian(date=start_run)
                je = jdatetime.date.fromgregorian(date=end_run)

                records.append({
                    'employee': emp,
                    'start_date': f"{js.year}-{js.month:02d}-{js.day:02d}",
                    'end_date': f"{je.year}-{je.month:02d}-{je.day:02d}",
                    'days': days,
                })

        if not records:
            messages.warning(
                request,
                _("No employees found with ≥20 consecutive absences in the past year.")
            )
            return redirect('permanent_absent_report')

        # 6) Global numbering
        for idx, rec in enumerate(records, start=1):
            rec['row_num'] = idx

        # 7) Paginate
        pages = chunked(records, page_size)

        # 8) Render
        jtoday = jdatetime.date.fromgregorian(date=today)
        jdate_str = f"{jtoday.year}-{jtoday.month}-{jtoday.day}"

        page_title = _("Permanent Absent Report")
        dept_name = Department.objects.get(pk=dept_id).name if dept_id else _("All Departments")
        work_type_nm = dict(work_types).get(work_type, _("All Types"))

        return render(request, 'reports/permanent_absent_report.html', {
            'page_title': page_title,
            'jdate_str': jdate_str,
            'pages': pages,
            'department_name': dept_name,
            'work_type_name': work_type_nm,
        })

    # GET → filter form
    return render(request, 'reports/permanent_absent_form.html', {
        'employees': all_emps,
        'departments': departments,
        'work_type_choices': work_types,
        'old': {},
    })

@login_required(login_url='login')
def test(request):
    return HttpResponse("test")

