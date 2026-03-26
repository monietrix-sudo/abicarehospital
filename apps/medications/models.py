"""
AbiCare - Medications Models
==============================
MedicationSchedule: A prescribed medication with a timetable.
MedicationDose: Each individual dose in the timetable.
Patients can tick doses as 'taken' from their portal.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class MedicationSchedule(models.Model):
    """
    A doctor's prescription: drug name, dosage, frequency, duration.
    Generates a timetable of MedicationDose entries.
    """

    FREQUENCY_CHOICES = [
        ('once', 'Once Daily'),
        ('twice', 'Twice Daily'),
        ('thrice', 'Three Times Daily'),
        ('four', 'Four Times Daily'),
        ('weekly', 'Weekly'),
        ('as_needed', 'As Needed (PRN)'),
    ]

    ROUTE_CHOICES = [
        ('oral', 'Oral'), ('iv', 'Intravenous'), ('im', 'Intramuscular'),
        ('topical', 'Topical'), ('inhaled', 'Inhaled'), ('sublingual', 'Sublingual'),
    ]

    patient = models.ForeignKey(
        'patients.Patient', on_delete=models.CASCADE, related_name='medication_schedules'
    )
    prescribed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='prescriptions',
        limit_choices_to={'role': 'doctor'}
    )

    drug_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100, help_text="e.g. 500mg, 5ml")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    route = models.CharField(max_length=20, choices=ROUTE_CHOICES, default='oral')
    start_date = models.DateField()
    end_date = models.DateField()
    instructions = models.TextField(blank=True, help_text="Special instructions (take with food, etc.)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.drug_name} ({self.dosage}) — {self.patient.full_name}"

    class Meta:
        verbose_name = "Medication Schedule"
        verbose_name_plural = "Medication Schedules"
        ordering = ['-created_at']


class MedicationDose(models.Model):
    """
    A single dose in a medication schedule.
    Patient ticks this off when they've taken the dose.
    """

    schedule = models.ForeignKey(
        MedicationSchedule, on_delete=models.CASCADE, related_name='doses'
    )
    scheduled_datetime = models.DateTimeField(help_text="When this dose should be taken.")
    taken = models.BooleanField(default=False)
    taken_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True, help_text="Patient note when ticking.")

    def mark_taken(self):
        """Mark this dose as taken now."""
        self.taken = True
        self.taken_at = timezone.now()
        self.save()

    def __str__(self):
        status = "✔" if self.taken else "○"
        return f"{status} {self.schedule.drug_name} @ {self.scheduled_datetime.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = "Medication Dose"
        verbose_name_plural = "Medication Doses"
        ordering = ['scheduled_datetime']
