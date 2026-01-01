from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def active_link(context, *args):
    """
    Usage in your template:
        {% active_link 'employees' 'add_employee' 'edit_employee' 'active' %}
    """
    # the last arg is the CSS class you want to output
    *url_names, css_class = args
    current = context['request'].resolver_match.url_name
    return css_class if current in url_names else ''
