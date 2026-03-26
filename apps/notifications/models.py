"""
AbiCare - Notifications Models
================================
In-app notification bell + email + browser push for:
- Overdue medication doses
- Appointment reminders (24hr and 1hr before)
- Record shares
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Notification(models.Model):
    """
    In-app notification stored per user.
    Shown in the notification bell in the topbar.
    """
    TYPE_CHOICES = [
        ('dose_overdue',        'Medication Overdue'),
        ('appointment_24hr',    'Appointment Reminder (24hr)'),
        ('appointment_1hr',     'Appointment Reminder (1hr)'),
        ('record_shared',       'Record Shared'),
        ('result_released',     'Lab Result Released'),
        ('teleconsult_approved','Teleconsult Approved'),
        ('general',             'General'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notif_type  = models.CharField(max_length=30, choices=TYPE_CHOICES, default='general')
    title       = models.CharField(max_length=200)
    message     = models.TextField()
    link        = models.CharField(max_length=300, blank=True, help_text="URL to navigate to on click")
    is_read     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    # Reference fields (optional — for linking back to the source object)
    patient_id      = models.IntegerField(null=True, blank=True)
    appointment_id  = models.IntegerField(null=True, blank=True)
    medication_id   = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.user.username} — {self.title}"


class NotificationPreference(models.Model):
    """Per-user notification settings."""
    user               = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notif_prefs')
    email_enabled      = models.BooleanField(default=True)
    inapp_enabled      = models.BooleanField(default=True)
    whatsapp_enabled   = models.BooleanField(default=False)
    whatsapp_number    = models.CharField(max_length=20, blank=True)
    dose_overdue       = models.BooleanField(default=True)
    appointment_remind = models.BooleanField(default=True)
    result_released    = models.BooleanField(default=True)

    def __str__(self):
        return f"Prefs for {self.user.username}"

    class Meta:
        verbose_name = "Notification Preference"
