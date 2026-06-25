import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('sonas')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'contract-expiration-check-daily': {
        'task': 'contrats.tasks.check_contract_expirations',
        'schedule': crontab(hour=8, minute=0),
    },
    'daily-notification-digest': {
        'task': 'notifications.tasks.send_daily_digest',
        'schedule': crontab(hour=9, minute=0),
    },
}
