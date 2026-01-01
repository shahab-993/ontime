from django.urls import path
from .views import (
    NotificationListView,
    MarkReadView,
    MarkAllReadView,
    ClearAllView,
)

app_name = "notifications"

urlpatterns = [
    path("", NotificationListView.as_view(), name="list"),
    path("read/<int:pk>/", MarkReadView.as_view(), name="mark_read"),
    path("read-all/", MarkAllReadView.as_view(), name="mark_all_read"),
    path("clear-all/", ClearAllView.as_view(), name="clear_all"),
]
