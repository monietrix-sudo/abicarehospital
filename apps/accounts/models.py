"""
AbiCare - Accounts Models
==========================
Custom User with hospital roles.
Includes PasswordResetRequest model — patient must get admin approval
before a reset link is sent.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid


class User(AbstractUser):

    ADMIN        = 'admin'
    DOCTOR       = 'doctor'
    NURSE        = 'nurse'
    LAB_TECH     = 'lab_tech'
    RECEPTIONIST = 'receptionist'
    PATIENT      = 'patient'

    ROLE_CHOICES = [
        (ADMIN,        'Administrator'),
        (DOCTOR,       'Doctor'),
        (NURSE,        'Nurse'),
        (LAB_TECH,     'Laboratory Technician'),
        (RECEPTIONIST, 'Receptionist'),
        (PATIENT,      'Patient'),
    ]

    role            = models.CharField(max_length=20, choices=ROLE_CHOICES, default=PATIENT)
    phone_number    = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='staff_photos/%Y/%m/', null=True, blank=True)
    department      = models.CharField(max_length=100, blank=True)
    license_number  = models.CharField(max_length=50, blank=True)
    is_active       = models.BooleanField(default=True)
    date_joined     = models.DateTimeField(default=timezone.now)

    @property
    def is_admin_staff(self):
        return self.role == self.ADMIN or self.is_superuser

    @property
    def is_doctor(self):
        return self.role == self.DOCTOR

    @property
    def is_nurse(self):
        return self.role == self.NURSE

    @property
    def is_lab_tech(self):
        return self.role == self.LAB_TECH

    @property
    def is_receptionist(self):
        return self.role == self.RECEPTIONIST

    @property
    def is_patient_user(self):
        return self.role == self.PATIENT

    @property
    def can_prescribe(self):
        return self.role in [self.DOCTOR, self.ADMIN]

    @property
    def can_approve_teleconsult(self):
        return self.role in [self.DOCTOR, self.ADMIN]

    @property
    def full_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    class Meta:
        verbose_name        = "User"
        verbose_name_plural = "Users"
        ordering = ['last_name', 'first_name']


class PasswordResetRequest(models.Model):
    """
    Patient requests a password reset.
    Admin must approve it before the reset link is sent.
    This prevents anyone from triggering reset emails without consent.
    """
    STATUS_CHOICES = [
        ('pending',  'Pending Admin Approval'),
        ('approved', 'Approved — Email Sent'),
        ('denied',   'Denied'),
        ('used',     'Used'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='reset_requests')
    token       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='reviewed_reset_requests')
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    expires_at   = models.DateTimeField(null=True, blank=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)

    @property
    def is_valid(self):
        from django.utils import timezone
        return (
            self.status == 'approved' and
            self.expires_at is not None and
            timezone.now() < self.expires_at
        )

    def __str__(self):
        return f"Reset request by {self.user.username} — {self.get_status_display()}"

    class Meta:
        ordering = ['-requested_at']
        verbose_name        = "Password Reset Request"
        verbose_name_plural = "Password Reset Requests"
