"""
AbiCare - Patients Models
==========================
Patient identity with:
- Auto-generated ABI hospital number
- Optional legacy/old hospital number field for existing patients
- Soft delete (is_active flag)
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


def patient_photo_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    return f"patient_photos/{timezone.now().strftime('%Y/%m')}/patient_{instance.patient_id}.{ext}"


class Patient(models.Model):

    BLOOD_GROUP_CHOICES = [
        ('A+','A+'),('A-','A-'),('B+','B+'),('B-','B-'),
        ('AB+','AB+'),('AB-','AB-'),('O+','O+'),('O-','O-'),
    ]
    GENOTYPE_CHOICES = [
        ('AA','AA'),('AS','AS'),('SS','SS'),('SC','SC'),('AC','AC'),
    ]
    GENDER_CHOICES   = [('M','Male'),('F','Female'),('O','Other')]
    MARITAL_CHOICES  = [
        ('single','Single'),('married','Married'),
        ('divorced','Divorced'),('widowed','Widowed'),
    ]

    patient_id      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    hospital_number = models.CharField(max_length=20, unique=True, help_text="Auto-generated e.g. ABI-2024-00001")

    # ── Legacy number field for existing patients ─────────────────────────────
    legacy_hospital_number = models.CharField(
        max_length=50, blank=True,
        verbose_name="Old/Previous Hospital Number",
        help_text="Enter the patient's existing hospital number if they were registered before this system."
    )

    user_account = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='patient_profile'
    )

    first_name      = models.CharField(max_length=100)
    middle_name     = models.CharField(max_length=100, blank=True)
    last_name       = models.CharField(max_length=100)
    date_of_birth   = models.DateField()
    gender          = models.CharField(max_length=1, choices=GENDER_CHOICES)
    marital_status  = models.CharField(max_length=10, choices=MARITAL_CHOICES, blank=True)
    nationality     = models.CharField(max_length=50, default='Nigerian')
    state_of_origin = models.CharField(max_length=50, blank=True)
    religion        = models.CharField(max_length=50, blank=True)
    occupation      = models.CharField(max_length=100, blank=True)

    photo = models.ImageField(upload_to=patient_photo_upload_path, null=True, blank=True)

    phone_number     = models.CharField(max_length=20)
    alt_phone_number = models.CharField(max_length=20, blank=True)
    email            = models.EmailField(blank=True)
    address          = models.TextField(blank=True)
    city             = models.CharField(max_length=100, blank=True)
    state            = models.CharField(max_length=100, blank=True)

    blood_group         = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True)
    genotype            = models.CharField(max_length=2, choices=GENOTYPE_CHOICES, blank=True)
    allergies           = models.TextField(blank=True)
    chronic_conditions  = models.TextField(blank=True)

    nok_name         = models.CharField(max_length=200, blank=True, verbose_name="Next of Kin Name")
    nok_relationship = models.CharField(max_length=50, blank=True, verbose_name="Relationship")
    nok_phone        = models.CharField(max_length=20, blank=True, verbose_name="Next of Kin Phone")
    nok_address      = models.TextField(blank=True, verbose_name="Next of Kin Address")

    assigned_doctor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_patients', limit_choices_to={'role': 'doctor'},
    )

    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    registered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='registered_patients',
    )

    @property
    def full_name(self):
        return ' '.join(p for p in [self.first_name, self.middle_name, self.last_name] if p)

    @property
    def age(self):
        today = timezone.now().date()
        dob   = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def display_number(self):
        """Show both numbers if legacy exists."""
        if self.legacy_hospital_number:
            return f"{self.hospital_number} (Old: {self.legacy_hospital_number})"
        return self.hospital_number

    def __str__(self):
        return f"{self.full_name} [{self.hospital_number}]"

    class Meta:
        verbose_name        = "Patient"
        verbose_name_plural = "Patients"
        ordering = ['-created_at']
