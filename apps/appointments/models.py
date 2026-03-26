"""
AbiCare - Appointments Models
==============================
Manages scheduled appointments, status tracking, and teleconsult authorization.
When a doctor marks an appointment 'completed' and approves teleconsult,
the patient gets access to the Zoom/Meet link.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Appointment(models.Model):
    """
    A scheduled consultation between a patient and doctor.
    Teleconsult link is only accessible after doctor authorization.
    """

    # ── Status workflow ───────────────────────────────────────────────────────
    # scheduled → confirmed → in_progress → completed
    #                       ↘ cancelled / no_show
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]

    TYPE_CHOICES = [
        ('in_person', 'In-Person Visit'),
        ('teleconsult', 'Teleconsultation'),
        ('follow_up', 'Follow-Up'),
        ('lab_review', 'Lab Review'),
        ('emergency', 'Emergency'),
    ]

    # ── Core fields ───────────────────────────────────────────────────────────
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    doctor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='doctor_appointments',
        limit_choices_to={'role': 'doctor'}
    )
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    appointment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='in_person')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    reason = models.TextField(help_text="Reason for the appointment.")
    notes = models.TextField(blank=True, help_text="Doctor's notes.")

    # ── Teleconsult fields ────────────────────────────────────────────────────
    # The link is stored here. Patient can only click it if teleconsult_approved=True.
    teleconsult_link = models.URLField(
        blank=True,
        help_text="Zoom or Google Meet link for this appointment."
    )
    teleconsult_approved = models.BooleanField(
        default=False,
        help_text="Doctor must set this True before patient can access the link."
    )
    teleconsult_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_teleconsults'
    )
    teleconsult_approved_at = models.DateTimeField(null=True, blank=True)

    # ── Session recording ─────────────────────────────────────────────────────
    allow_recording = models.BooleanField(
        default=False,
        help_text="Doctor can enable session recording for this appointment."
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    booked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='booked_appointments'
    )

    @property
    def is_today(self):
        return self.appointment_date == timezone.now().date()

    @property
    def can_join_teleconsult(self):
        """Patient can only join if approved AND appointment type is teleconsult."""
        return self.teleconsult_approved and self.appointment_type == 'teleconsult'

    def __str__(self):
        return f"{self.patient.full_name} — Dr. {self.doctor.get_full_name()} on {self.appointment_date}"

    class Meta:
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"
        ordering = ['-appointment_date', '-appointment_time']
