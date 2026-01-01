from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from employee.models import Employee
from users.models import User


class Device(models.Model):
    class DeviceType(models.TextChoices):
        ATTENDANCE = 'AT', _('Attendance')
        REGISTRATION = 'RG', _('Registration')

    class Status(models.TextChoices):
        ENABLED = 'enabled', _('Enabled')
        DISABLED = 'disabled', _('Disabled')

    # a human‐friendly unique identifier
    identifier = models.CharField(
        _('Device ID'),
        max_length=50,
        unique=True,
        help_text=_('Your internal device code, e.g. "DEV123"')
    )

    name = models.CharField(
        _('Device Name'),
        max_length=150,
        help_text=_('E.g. "Front Gate Scanner"')
    )

    ip_address = models.GenericIPAddressField(
        _('IP Address'),
        protocol='both',
        unpack_ipv4=True,
        help_text=_('IPv4 or IPv6 address of the device')
    )

    port = models.PositiveIntegerField(
        _('Port'),
        default=4370,
        help_text=_('Typically 4370 for ZKTeco devices')
    )

    com_key = models.PositiveIntegerField(
        _('Communication Key'),
        default=0,
        help_text=_('Device communication key (numeric)')
    )

    device_type = models.CharField(
        _('Type'),
        max_length=2,
        choices=DeviceType.choices,
        default=DeviceType.ATTENDANCE
    )

    status = models.CharField(
        _('Status'),
        max_length=8,
        choices=Status.choices,
        default=Status.ENABLED,
        help_text=_('Whether this device is active or not')
    )

    # optional free-text notes (e.g. location, firmware version…)
    description = models.TextField(
        _('Description'),
        blank=True
    )

    # row timestamps
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Device')
        verbose_name_plural = _('Devices')
        ordering = ['name']
        default_permissions = ()  # disable add/change/delete/view
        indexes = [
            models.Index(fields=['identifier']),
            models.Index(fields=['ip_address', 'port']),
        ]

    def __str__(self):
        return f"{self.name} ({self.identifier})"


class BiometricRecord(models.Model):
    class BiometricType(models.TextChoices):
        FINGERPRINT = 'FP', _('Fingerprint')
        FACE = 'FA', _('Face')
        IRIS = 'IR', _('Iris')
        RFID = 'RF', _('RFID Card')

    class FingerPosition(models.IntegerChoices):
        RIGHT_THUMB = 0, _('Right Thumb')
        RIGHT_INDEX = 1, _('Right Index')
        RIGHT_MIDDLE = 2, _('Right Middle')
        RIGHT_RING = 3, _('Right Ring')
        RIGHT_LITTLE = 4, _('Right Little')
        LEFT_THUMB = 5, _('Left Thumb')
        LEFT_INDEX = 6, _('Left Index')
        LEFT_MIDDLE = 7, _('Left Middle')
        LEFT_RING = 8, _('Left Ring')
        LEFT_LITTLE = 9, _('Left Little')

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='biometric_records',
        verbose_name=_('Employee')
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='biometric_records',
        verbose_name=_('Registered On Device')
    )
    biometric_type = models.CharField(
        _('Biometric Type'),
        max_length=2,
        choices=BiometricType.choices,
        default=BiometricType.FINGERPRINT
    )
    finger_position = models.PositiveSmallIntegerField(
        _('Finger Position'),
        choices=FingerPosition.choices,
        null=True,
        blank=True,
        help_text=_('Which finger (if applicable)')
    )
    template_data = models.TextField(
        _('Template Data'),
        help_text=_('Raw template blob or serialized string from device')
    )

    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Biometric Record')
        verbose_name_plural = _('Biometric Records')
        default_permissions = ()  # disable add/change/delete/view
        unique_together = [
            ('employee', 'biometric_type', 'finger_position'),
        ]
        ordering = ['employee', 'biometric_type', 'finger_position']

    def __str__(self):
        name = self.employee.user.get_full_name() or self.employee.employee_id
        # show finger position if available
        if self.finger_position is not None:
            pos = self.get_finger_position_display()
            return f"{name} – {self.get_biometric_type_display()} ({pos})"
        return f"{name} – {self.get_biometric_type_display()}"


class AttendanceLog(models.Model):
    class LogType(models.TextChoices):
        CLOCK_IN = 'IN', _('Clock In')
        CLOCK_OUT = 'OUT', _('Clock Out')

    class VerificationType(models.TextChoices):
        FINGERPRINT = 'FP', _('Fingerprint')
        FACE = 'FA', _('Face')
        IRIS = 'IR', _('Iris')
        CARD = 'CA', _('Card/RFID')
        PIN = 'PN', _('Password/PIN')
        MANUAL = 'MN', _('Manual Entry')

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='attendance_logs',
        verbose_name=_('Employee')
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_logs',
        verbose_name=_('Device')
    )
    timestamp = models.DateTimeField(
        _('Event Time'),
        help_text=_('When the punch was recorded')
    )
    log_type = models.CharField(
        _('Type'),
        max_length=3,
        choices=LogType.choices,
        null=True, blank=True,
        help_text=_('Clock-in or clock-out')
    )
    status = models.DecimalField(
        _('Status'),
        max_digits=3,
        decimal_places=0,
        null=True,
        blank=True,
        help_text=_('Attendance log status')
    )

    verification_type = models.CharField(
        _('Verification Method'),
        max_length=2,
        choices=VerificationType.choices,
        default=VerificationType.FINGERPRINT,
        help_text=_('Which modality or manual entry was used')
    )

    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)

    class Meta:
        verbose_name = _('Attendance Log')
        verbose_name_plural = _('Attendance Logs')
        ordering = ['-timestamp']
        default_permissions = ()  # disable add/change/delete/view
        indexes = [models.Index(fields=['timestamp'])]
        unique_together = [
            ('employee', 'timestamp', 'device')
        ]

    def __str__(self):
        name = self.employee.user.get_full_name() or self.employee.employee_id
        return (
            f"{name} — {self.get_log_type_display()} @ "
            f"{self.timestamp:%Y-%m-%d %H:%M} ({self.get_verification_type_display()})"
        )


class EmployeeVacation(models.Model):
    class VacationType(models.TextChoices):
        PASTIME = 'PT', _('Pastime Leave')
        SICK = 'SC', _('Sick Leave')
        NATIVITY_SICK = 'NS', _('Maternity/Paternity Leave')
        URGENCY = 'UR', _('Emergency Leave')
        DEFICIT_SALARY = 'DS', _('Salary Deduction')
        DUTY = 'DY', _('Duty Assignment')
        HAJ = 'HJ', _('Hajj Leave')
        GENERAL_HOLIDAY = 'GH', _('Public Holiday')
        CONSIDERATIONS = 'CA', _('Considerations')

    class Status(models.TextChoices):
        PENDING = 'P', _('Pending')
        APPROVED = 'A', _('Approved')
        REJECTED = 'R', _('Rejected')

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name="vacations",
        verbose_name=_("Employee")
    )
    type = models.CharField(
        _("Type of Leave"),
        max_length=2,
        choices=VacationType.choices
    )
    start_date = models.DateField(_("Start Date"))
    end_date = models.DateField(_("End Date"))
    days_requested = models.DecimalField(
        _("Days Requested"),
        max_digits=5, decimal_places=2,
        help_text=_("Number of working days taken")
    )
    reason = models.TextField(
        _("Reason"), blank=True,
        help_text=_("Optional justification or details")
    )
    attachment = models.FileField(
        _("Attachment"), blank=True, null=True,
        help_text=_("Supporting document (e.g. doctor’s note)")
    )
    status = models.CharField(
        _("Status"), max_length=1,
        choices=Status.choices, default=Status.PENDING
    )
    requested_at = models.DateTimeField(_("Requested At"), auto_now_add=True)
    processed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_("Processed By"),
        help_text=_("Supervisor or HR who approved/rejected")
    )
    processed_at = models.DateTimeField(
        _("Processed At"), null=True, blank=True
    )

    class Meta:
        ordering = ["-start_date"]
        verbose_name = _("Employee Vacation")
        verbose_name_plural = _("Employee Vacations")
        default_permissions = ()  # disable add/change/delete/view
        # Prevent duplicate requests for the same employee/type/date-range:
        unique_together = [
            ("employee", "type", "start_date", "end_date")
        ]

    def __str__(self):
        return (
            f"{self.employee} – {self.get_type_display()} "
            f"{self.start_date:%Y-%m-%d}→{self.end_date:%Y-%m-%d}"
        )

    def get_absolute_url(self):
        return reverse('employee_leave')


class DailyLeave(models.Model):
    class LeaveType(models.TextChoices):
        CLOCK_IN = 'CI', _('Clock-In Only')
        CLOCK_OUT = 'CO', _('Clock-Out Only')
        CLOCK_IN_OUT = 'CB', _('Clock-In & Clock-Out')

    class Status(models.TextChoices):
        PENDING = 'P', _('Pending')
        ACCEPTED = 'A', _('Accepted')
        REJECTED = 'R', _('Rejected')

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='daily_leaves',
        verbose_name=_('Employee')
    )

    # The date the leave is for
    date = models.DateField(
        verbose_name=_('Date of Leave'),
        null=True,
        blank=True
    )

    # Now a single choice instead of two datetime fields
    leave_type = models.CharField(
        max_length=2,
        choices=LeaveType.choices,
        default=LeaveType.CLOCK_IN_OUT,
        verbose_name=_('Leave Type')
    )

    # Why they’re taking this leave
    reason = models.TextField(
        verbose_name=_('Reason'),
        blank=True
    )

    head_of_department = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'employee_profile__is_head_of_dep': True},
        verbose_name=_('Head of Department'),
        help_text=_('Must be a user marked as head_of_dep')
    )

    status = models.CharField(
        max_length=1,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('Status')
    )

    requested_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Requested At')
    )
    processed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Processed At')
    )

    class Meta:
        verbose_name = _('Daily Leave')
        verbose_name_plural = _('Daily Leaves')
        ordering = ['-requested_at']
        default_permissions = ()  # disable add/change/delete/view

    def __str__(self):
        return f"{self.employee.employee_id} – {self.get_leave_type_display()} – {self.get_status_display()}"

    def get_absolute_url(self):
        # this should resolve to path('daily_leave/', …, name='daily_leave')
        return reverse('daily_leave')
