from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from users.models import User


class Shift(models.Model):
    name = models.CharField(_('Shift Name'), max_length=50, unique=True)
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_shifts',
        verbose_name=_('Created By')
    )
    is_active = models.BooleanField(_('Active'), default=True)

    # row timestamps
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Shift')
        verbose_name_plural = _('Shifts')
        ordering = ['id']
        default_permissions = ()  # disable add/change/delete/view

    def __str__(self):
        return self.name


class ShiftSchedule(models.Model):
    class DayOfWeek(models.IntegerChoices):
        SATURDAY = 1, _('Saturday')
        SUNDAY = 2, _('Sunday')
        MONDAY = 3, _('Monday')
        TUESDAY = 4, _('Tuesday')
        WEDNESDAY = 5, _('Wednesday')
        THURSDAY = 6, _('Thursday')
        FRIDAY = 7, _('Friday')

    shift = models.ForeignKey(
        Shift, on_delete=models.CASCADE, related_name='schedules', verbose_name=_('Shift')
    )
    year = models.PositiveIntegerField(
        _('Year'),
        validators=[MinValueValidator(1300), MaxValueValidator(9999)],
        help_text=_('4-digit calendar year this schedule applies to')
    )
    month = models.PositiveSmallIntegerField(
        _('Month'),
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text=_('Month of year (1–12) that this schedule applies to')
    )
    day_of_week = models.PositiveSmallIntegerField(
        _('Day of Week'),
        choices=DayOfWeek.choices,
    )

    in_start_time = models.TimeField(_('Clock-in Start'), null=True, blank=True)
    in_end_time = models.TimeField(_('Clock-in End'), null=True, blank=True)
    out_start_time = models.TimeField(_('Clock-out Start'), null=True, blank=True)
    out_end_time = models.TimeField(_('Clock-out End'), null=True, blank=True)

    is_active = models.BooleanField(
        _('Active'),
        default=True,
        help_text=_('Uncheck to disable this schedule without deleting it')
    )

    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_shift_schedules',
        verbose_name=_('Created By')
    )

    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Shift Schedule')
        verbose_name_plural = _('Shift Schedules')
        default_permissions = ()  # disable add/change/delete/view
        ordering = ['year', 'month', 'day_of_week', 'in_start_time']
        unique_together = [
            ('shift', 'year', 'month', 'day_of_week'),
        ]

    def __str__(self):
        dow = self.get_day_of_week_display()
        # safely format each time or use a placeholder if None
        in_start = self.in_start_time.strftime("%H:%M") if self.in_start_time else "--:--"
        in_end = self.in_end_time.strftime("%H:%M") if self.in_end_time else "--:--"
        out_start = self.out_start_time.strftime("%H:%M") if self.out_start_time else "--:--"
        out_end = self.out_end_time.strftime("%H:%M") if self.out_end_time else "--:--"
        return (
            f"{self.shift.name} | {self.year}-{self.month:02d} – "
            f"{dow} "
            f"{in_start}-{in_end} / {out_start}-{out_end}"
        )


class Department(models.Model):
    name = models.CharField(_('Department Name'), max_length=150, unique=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Department')
        verbose_name_plural = _('Departments')
        ordering = ['name']
        default_permissions = ()  # disable add/change/delete/view

    def __str__(self):
        return self.name


class Employee(models.Model):
    FULL_TIME = 'FT'
    PART_TIME = 'PT'
    CONTRACTOR = 'CT'
    INTERN = 'IN'
    WORK_TYPE_CHOICES = [
        (FULL_TIME, _('Full-Time')),
        (PART_TIME, _('Part-Time')),
        (CONTRACTOR, _('Contractor')),
        (INTERN, _('Intern')),
    ]

    user = models.OneToOneField(
        User, verbose_name=_('User Account'),
        on_delete=models.CASCADE,
        related_name='employee_profile'
    )
    employee_id = models.DecimalField(
        _('Employee ID'),
        max_digits=15,
        decimal_places=0,
        unique=True,
        blank=True, null=True,
        help_text=_('Custom ID to print on badges/cards')
    )
    father_name = models.CharField(_('Father’s Name'), max_length=100, blank=True)
    grand_father_name = models.CharField(_('Grandfather’s Name'), max_length=100, blank=True)
    position = models.CharField(_('Position/Title'), max_length=150, blank=True)
    is_device_admin = models.BooleanField(
        _('Device Administrator'),
        default=False,
        help_text=_('If true, this user is the admin of biometric devices')
    )
    department = models.ForeignKey(
        Department, verbose_name=_('Department'),
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employees'
    )
    is_head_of_dep = models.BooleanField(
        _('Head of Department'),
        default=False,
        help_text=_('If true, this user is the head of their department')
    )
    bast = models.CharField(_('Bast Code'), max_length=50, blank=True)
    qua_dam = models.CharField(_('Qua Dam Code'), max_length=50, blank=True)
    legacy_code = models.CharField(_('Legacy Code'), max_length=50, blank=True)
    contract_date = models.CharField(_('Contract Date'), max_length=50, blank=True)
    education_degree = models.CharField(_('Education Degree'), max_length=50, blank=True)
    national_id = models.CharField(_('National ID'), max_length=50, blank=True)
    shift = models.ForeignKey(
        Shift, verbose_name=_('Assigned Shift'),
        on_delete=models.SET_NULL, null=True, blank=True
    )
    work_type = models.CharField(
        _('Work Type'),
        max_length=2,
        choices=WORK_TYPE_CHOICES,
        default=FULL_TIME
    )
    salary = models.DecimalField(
        _('Salary'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Monthly salary or contract amount')
    )
    duty_days = models.PositiveSmallIntegerField(
        _('Duty Days'),
        default=0,
        help_text=_('Working days per month')
    )
    is_archive = models.BooleanField(
        _('Archived'),
        default=False,
        help_text=_('Mark if no longer active')
    )

    archive_date = models.DateField(
        _('Archive Date'),
        null=True, blank=True,
        help_text=_('When this employee was archived')
    )
    archive_reason = models.TextField(
        _('Archive Reason'),
        blank=True,
        help_text=_('Reason for archiving this employee')
    )
    is_active = models.BooleanField(
        _('Active'),
        default=True,
        help_text=_('Uncheck to disable this employee without deleting them')
    )

    extra_info = models.TextField(
        _('Additional Info'),
        blank=True,
        help_text=_('Free-form notes')
    )

    address = models.TextField(
        _('Address'),
        blank=True,
        help_text=_('Employee’s full mailing address')
    )

    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Employee')
        verbose_name_plural = _('Employees')
        default_permissions = ()  # disable add/change/delete/view
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class EmployeeDocument(models.Model):
    employee = models.ForeignKey(
        Employee, verbose_name=_('Employee'),
        on_delete=models.CASCADE,
        related_name='documents'
    )
    file = models.FileField(
        _('Document'),
        upload_to='employee_docs/%Y/%m/%d/'
    )
    description = models.CharField(
        _('Description'),
        max_length=255,
        blank=True,
        help_text=_('Optional note about this file')
    )
    uploaded_at = models.DateTimeField(_('Uploaded At'), auto_now_add=True)

    class Meta:
        verbose_name = _('Employee Document')
        verbose_name_plural = _('Employee Documents')
        ordering = ['-uploaded_at']
        default_permissions = ()  # disable add/change/delete/view

    def __str__(self):
        # if file has already been removed, avoid calling `.name`
        if self.file and hasattr(self.file, 'name'):
            filename = self.file.name.rsplit('/', 1)[-1]
        else:
            filename = '(no file)'
        return f"{self.employee} — {filename}"
