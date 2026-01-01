from django.db import models
from django.utils.translation import gettext_lazy as _

class GlobalPermission(models.Model):
    """
    Dummy model just to hang our app-wide custom permissions on.
    """

    class Meta:
        managed = False  # Django won’t try to create a table
        default_permissions = ()  # disable add/change/delete/view
        permissions = [
            # dashboard permissions
            ('view_admin_dashboard',     _('View the admin dashboard')),
            ('view_employee_dashboard',       _('View the employee dashboard')),
            ('view_hod_dashboard',       _('View the head of department dashboard')),

            # employee permissions
            ('view_employee_list',       _('View the employee list')),
            ('add_employee',             _('Add employee')),
            ('change_employee',          _('Change employee')),
            ('delete_employee',          _('Delete employee')),

            # employee profile permissions
            ('view_employee_profile',    _('View employee profile')),

            ('view_employee_documents',    _('View employee documents')),
            ('add_employee_documents',    _('Add employee documents')),
            ('delete_employee_documents',    _('Delete employee documents')),

            ('change_employee_password',    _('Change employee password')),
            ('view_employee_biometric', _('View employee biometric data')),
            ('change_employee_biometric', _('Change employee biometric data')),
            ('view_employee_settings', _('View employee settings')),

            # employee archive permissions
            ('view_employee_archive_list', _('View the archive employee list')),
            ('delete_employee_archive',  _('Delete the archive employee')),

            # department permissions
            ('view_department_list',     _('View the department list')),
            ('add_department',           _('Add the department')),
            ('change_department',        _('Change the department')),
            ('delete_department',        _('Delete the department')),

            # shift permissions
            ('view_shift_list',          _('View the shift list')),
            ('add_shift',                _('Add the shift')),
            ('change_shift',             _('Change the shift')),
            ('delete_shift',             _('Delete the shift')),

            # report permissions
            ('check_attendance',         _('Check employee attendance')),
            ('view_daily_attendance',    _('View the daily attendance')),
            ('view_daily_report_all_employee_by_hod',    _('View department-based employee list by the head of department in daily attendance')),
            ('view_monthly_attendance',  _('View the monthly attendance')),
            ('view_monthly_report_all_employee_by_hod', _('View department-based employee list by the head of department in Monthly attendance')),
            ('view_attendance_report',   _('View the attendance report')),
            ('view_employee_list_report',   _('View the employee list report for print')),
            ('view_permanent_absent_report',   _('View the permanent absent report')),

            # Leave permissions
            ('view_public_holiday_list', _('View the public holiday list')),
            ('add_public_holiday',       _('Add the public holiday')),
            ('delete_public_holiday',    _('Delete the public holiday')),

            ('view_employee_leave_list', _('View the employee leave list')),
            ('view_employee_leave_details', _('View the employee leave details')),
            ('confirm_employee_leave',   _('Confirm the employee leave')),
            ('add_employee_leave',       _('Add the employee leave')),
            ('delete_employee_leave',    _('Delete the employee leave')),

            ('view_daily_leave_list',    _('View the daily leave list')),
            ('view_daily_leave_details', _('View the daily leave details')),
            ('confirm_daily_leave',      _('Confirm the daily leave')),
            ('add_daily_leave',          _('Add the daily leave')),
            ('delete_daily_leave',       _('Delete the daily leave')),

            ('view_make_absent',       _('Employees to be marked as absent')),
            ('view_make_present',       _('Employees to be marked as attend')),

            # device permissions
            ('view_device_list',         _('View the device list')),
            ('view_device',               _('View device details')),
            ('add_device',               _('Add device')),
            ('change_device',            _('Change device')),
            ('delete_device',            _('Delete device')),

            # user permissions
            ('view_user_list',           _('View the users list')),
            ('add_user',                 _('Add user')),
            ('change_user',              _('Change user')),
            ('delete_user',              _('Delete user')),

            ('view_roles_list',          _('View the roles list')),
            ('add_role',                 _('Add role')),
            ('change_role',              _('Change role')),
            ('delete_role',              _('Delete role')),

            ('view_activity_log_list',   _('View the activity logs')),
            ('view_backup',              _('View the backup option')),
        ]
