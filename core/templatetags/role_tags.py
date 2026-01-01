from django import template

register = template.Library()

@register.filter
def in_group(user, group_name):
    """
    Usage in template:
      {% if request.user|in_group:"Employee" %}
         … show employee-only stuff …
      {% endif %}
    """
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()
