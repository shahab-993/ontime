from django.urls import path
from . import views

urlpatterns = [
    path('employees', views.employees, name='employees'),
    path('fetch_employees', views.fetch_employees, name='fetch_employees'),

    path('employee/<int:employee_id>/toggle-archive/', views.ajax_toggle_archive, name='ajax_toggle_archive'),
    path('emp_archive', views.emp_archive, name='emp_archive'),
    path('fetch_emp_archive', views.fetch_emp_archive, name='fetch_emp_archive'),

    path('update_employee_status', views.update_employee_status, name='update_employee_status'),
    path('delete_employee', views.delete_employee, name='delete_employee'),
    path('add_employee', views.add_employee, name='add_employee'),
    path('edit_employee/<str:employee_id>', views.edit_employee, name='edit_employee'),
    path('employee_profile/<int:employee_id>', views.employee_profile, name='employee_profile'),
    path('emp_archive_profile/<int:employee_id>', views.employee_profile, name='emp_archive_profile'),
    path('my-profile/', views.employee_profile, name='my-profile'),
    path('ajax_change_employee_password/<int:employee_id>', views.ajax_change_employee_password, name='ajax_change_employee_password'),

    path('ajax_upload_employee_document/<int:employee_id>', views.ajax_upload_employee_document, name='ajax_upload_employee_document'),
    path('ajax_delete_employee_document/<int:doc_id>/delete/', views.ajax_delete_employee_document, name='ajax_delete_employee_document'),

    path('departments', views.departments, name='departments'),
    path('fetch_departments', views.fetch_departments, name='fetch_departments'),
    path('delete_department', views.delete_department, name='delete_department'),
    path('add_department', views.add_department, name='add_department'),
    path('edit_department/<str:dept_id>', views.edit_department, name='edit_department'),

    path('shifts', views.shifts, name='shifts'),
    path('fetch_shifts', views.fetch_shifts, name='fetch_shifts'),

    path('fetch_shift_years', views.fetch_shift_years, name='fetch_shift_years'),
    path('add_shift_year', views.add_shift_year, name='add_shift_year'),
    path('delete_shift_year', views.delete_shift_year, name='delete_shift_year'),

    path('delete_shift', views.delete_shift, name='delete_shift'),
    path('add_shift', views.add_shift, name='add_shift'),
    path('edit_shift/<str:shift_id>', views.edit_shift, name='edit_shift'),
    path('view_shift/<str:shift_id>', views.view_shift, name='view_shift'),

]
