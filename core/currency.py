"""Formatage monétaire USD pour toute l'application."""

from decimal import Decimal, InvalidOperation


def format_usd(amount) -> str:
    if amount is None or amount == '':
        return '—'
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        return '—'
    return f'${value:,.2f}'
