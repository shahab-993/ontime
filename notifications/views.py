# notifications/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Notification


class NotificationListView(ListView):
    model = Notification
    template_name = "notifications/list.html"
    paginate_by = 20

    def get_queryset(self):
        return self.request.user.notifications.all()


class MarkReadView(View):
    def post(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notif.mark_read()
        return JsonResponse({"status": "ok"})


class MarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        request.user.notifications.filter(unread=True).update(unread=False)
        return JsonResponse({"status": "ok"})


class ClearAllView(LoginRequiredMixin, View):
    def post(self, request):
        request.user.notifications.all().delete()
        return JsonResponse({"status": "ok"})
