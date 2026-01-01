from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include, re_path
from django.views.i18n import JavaScriptCatalog
from django.views.static import serve

from core import views

urlpatterns = [
    # your other non‐i18n URLs…
    path('i18n/', include('django.conf.urls.i18n')),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
]
urlpatterns += [
    # path('admin/', admin.site.urls),
    path('', include('users.urls')),
    path('emp/', include('employee.urls')),
    path('attendance/', include('attendance.urls')),

    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard_data/', views.dashboard_data, name='dashboard_data'),

    path("notifications/", include("notifications.urls", namespace="notifications")),

    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
