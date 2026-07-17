from django import template

from core.currency import format_usd

register = template.Library()


@register.filter(name='usd')
def usd(value):
    """Affiche un montant en dollars américains : $1,234.56"""
    return format_usd(value)
