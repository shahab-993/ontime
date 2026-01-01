from django.urls import path
from . import views

urlpatterns = [
    path('devices', views.devices, name='devices'),
    path('delete_device', views.delete_device, name='delete_device'),
    path('add_device', views.add_device, name='add_device'),
    path('edit_device/<str:device_id>', views.edit_device, name='edit_device'),
    path('view_device/<str:device_id>', views.view_device, name='view_device'),
# urls.py
    path('fetch_device_stats/<int:device_id>', views.fetch_device_stats, name='fetch_device_stats'),
    path('devices/<int:device_id>/status/', views.check_device_status, name='check_device_status'),
    path('devices/sync-time/', views.sync_devices_time, name='sync_devices_time'),

    path('devices/delete-users/', views.delete_device_users, name='delete_device_users'),
    path('upload_all_to_device', views.upload_all_biometrics_to_device, name='upload_all_to_device'),
    path('check_upload_progress', views.check_upload_progress, name='check_upload_progress'),
    path('download_biometric_data', views.download_biometric_data, name='download_biometric_data'),
    path('upload_biometric_data', views.upload_biometric_data, name='upload_biometric_data'),
    path('delete_biometric_data', views.delete_biometric_data, name='delete_biometric_data'),
    path("delete_biometric_db", views.delete_biometric_db, name="delete_biometric_db"),


    path('public_holidays', views.public_holidays, name='public_holidays'),
    path('fetch_public_holidays', views.fetch_public_holidays, name='fetch_public_holidays'),
    path('delete_public_holiday', views.delete_public_holiday, name='delete_public_holiday'),
    path('add_public_holiday', views.add_public_holiday, name='add_public_holiday'),

    path('employee_leave', views.employee_leave, name='employee_leave'),
    path('fetch_employee_leaves', views.fetch_employee_leaves, name='fetch_employee_leaves'),
    path('delete_employee_leave', views.delete_employee_leave, name='delete_employee_leave'),
    path('add_employee_leave', views.add_employee_leave, name='add_employee_leave'),
    path('get_employee_leave/<int:leave_id>/', views.get_employee_leave, name='get_employee_leave'),
    path('update_employee_leave_status', views.update_employee_leave_status, name='update_employee_leave_status'),
    path('daily_leave/', views.daily_leave, name='daily_leave'),
    path('fetch_daily_leaves/', views.fetch_daily_leaves, name='fetch_daily_leaves'),
    path('get_daily_leave/<int:leave_id>/', views.get_daily_leave, name='get_daily_leave'),
    path('update_daily_leave_status/', views.update_daily_leave_status, name='update_daily_leave_status'),
    path('add_daily_leave', views.add_daily_leave, name='add_daily_leave'),
    path('delete_daily_leave', views.delete_daily_leave, name='delete_daily_leave'),

    path('make_absent', views.make_absent, name='make_absent'),
    path('make_present', views.make_present, name='make_present'),

    # report section
    path('check_attendance', views.check_attendance, name='check_attendance'),
    path('daily_attendance', views.daily_attendance, name='daily_attendance'),
    path('monthly_attendance', views.monthly_attendance, name='monthly_attendance'),
    path('attendance_report', views.attendance_report, name='attendance_report'),

    path('employee_report', views.employee_report, name='employee_report'),
    path('permanent_absent_report', views.permanent_absent_report, name='permanent_absent_report'),
    path('test', views.test, name='test'),

]
