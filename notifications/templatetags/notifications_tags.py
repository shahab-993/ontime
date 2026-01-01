# notifications/templatetags/notifications_tags.py
import datetime


from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def unread_count(context):
    return context["request"].user.notifications.filter(unread=True).count()


@register.inclusion_tag("notifications/dropdown.html", takes_context=True)
def notifications_dropdown(context, limit=5):
    user = context["request"].user
    qs   = user.notifications.all()[:limit]
    unread = user.notifications.filter(unread=True).count()

    # Use plain Python dates to avoid naive‐datetime / timezone conflicts
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    return {
        "notifications": qs,
        "unread_count": unread,
        "today": today,
        "yesterday": yesterday,
        "csrf_token": context["csrf_token"],
    }
