from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Journal des actions internes (agents, gérants) visible par l'admin."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    username = models.CharField(max_length=150)
    role = models.CharField(max_length=10, blank=True)
    action = models.CharField(max_length=120)
    method = models.CharField(max_length=10, default='POST')
    path = models.CharField(max_length=500)
    status_code = models.PositiveSmallIntegerField(default=200)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Journal audit'
        verbose_name_plural = 'Journaux audit'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.username} — {self.action}'
