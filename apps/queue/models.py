"""
AbiCare - Waiting Room Queue
==============================
Daily queue that resets each morning.
Patients get a queue number when they arrive.
Receptionists/nurses call the next patient with one click.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class QueueEntry(models.Model):
    """One entry in today's waiting room queue."""

    STATUS_CHOICES = [
        ('waiting',    'Waiting'),
        ('called',     'Called'),
        ('with_doctor','With Doctor'),
        ('done',       'Done'),
        ('skipped',    'Skipped'),
    ]

    patient         = models.ForeignKey('patients.Patient', on_delete=models.CASCADE,
                                        related_name='queue_entries')
    queue_date      = models.DateField(default=timezone.now)
    queue_number    = models.PositiveIntegerField()
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    check_in_time   = models.DateTimeField(auto_now_add=True)
    called_at       = models.DateTimeField(null=True, blank=True)
    called_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='called_queue_entries')
    doctor          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='queue_doctor_entries',
                                        limit_choices_to={'role': 'doctor'})
    appointment     = models.ForeignKey('appointments.Appointment', on_delete=models.SET_NULL,
                                        null=True, blank=True)
    notes           = models.CharField(max_length=200, blank=True)
    added_by        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                        related_name='added_queue_entries')
    self_checkin    = models.BooleanField(default=False, help_text="True if patient checked in themselves")

    class Meta:
        ordering = ['queue_number']
        unique_together = [['queue_date', 'queue_number']]
        verbose_name        = "Queue Entry"
        verbose_name_plural = "Queue Entries"

    def __str__(self):
        return f"#{self.queue_number} — {self.patient.full_name} ({self.queue_date})"

    @classmethod
    def next_number_for_today(cls):
        """Get the next queue number for today."""
        today   = timezone.now().date()
        last    = cls.objects.filter(queue_date=today).order_by('-queue_number').first()
        return (last.queue_number + 1) if last else 1
