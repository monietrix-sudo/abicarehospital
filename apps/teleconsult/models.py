"""
AbiCare - Teleconsult Models
==============================
The teleconsult link lives on the Appointment model.
This app manages link presets that doctors/admins can reuse
(e.g. a permanent Zoom room for a specific doctor).
"""
from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()


class ConsultLink(models.Model):
    """A saved, reusable Zoom or Google Meet link for a doctor."""
    PLATFORM_CHOICES = [('zoom', 'Zoom'), ('meet', 'Google Meet'), ('other', 'Other')]
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consult_links',
                               limit_choices_to={'role': 'doctor'})
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    link = models.URLField()
    label = models.CharField(max_length=100, default='Default Room')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.doctor.get_full_name()} — {self.label} ({self.get_platform_display()})"

    class Meta:
        verbose_name = "Consult Link"
        verbose_name_plural = "Consult Links"
