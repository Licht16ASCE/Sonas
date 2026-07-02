from django import template

from notifications.services import get_content_object_url

register = template.Library()


@register.simple_tag
def content_object_url(user, obj):
    return get_content_object_url(user, obj)
