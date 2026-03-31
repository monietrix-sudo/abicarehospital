"""
AbiCare - Patients Models
==========================
Global EHR-standard patient registration.
Core required fields: first_name, last_name, phone_number, gender, date_of_birth
Everything else is optional and editable later.
Fields with dummy/PENDING values from import are flagged with has_pending_fields=True.
"""

import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


def patient_photo_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    return f"patient_photos/{timezone.now().strftime('%Y/%m')}/patient_{instance.patient_id}.{ext}"


class Patient(models.Model):

    # ── Choice lists ──────────────────────────────────────────────────
    BLOOD_GROUP_CHOICES = [
        ('A+','A+'),('A-','A-'),('B+','B+'),('B-','B-'),
        ('AB+','AB+'),('AB-','AB-'),('O+','O+'),('O-','O-'),
    ]
    GENOTYPE_CHOICES = [
        ('AA','AA'),('AS','AS'),('SS','SS'),('SC','SC'),('AC','AC'),
    ]
    GENDER_CHOICES = [('M','Male'),('F','Female'),('O','Other/Prefer not to say')]
    MARITAL_CHOICES = [
        ('single','Single'),('married','Married'),
        ('divorced','Divorced'),('widowed','Widowed'),
        ('separated','Separated'),('unknown','Unknown'),
    ]
    RELATIONSHIP_CHOICES = [
        ('father','Father'),('mother','Mother'),('spouse','Spouse'),
        ('sibling','Sibling'),('child','Child'),('guardian','Guardian'),
        ('friend','Friend'),('other','Other'),
    ]
    RELIGION_CHOICES = [
        ('christianity','Christianity'),('islam','Islam'),
        ('traditional','Traditional'),('other','Other'),('none','None'),
    ]

    # ── Identity ──────────────────────────────────────────────────────
    patient_id      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    hospital_number = models.CharField(max_length=20, unique=True)
    legacy_hospital_number = models.CharField(max_length=50, blank=True,
        verbose_name="Old/Previous Hospital Number")
    user_account    = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='patient_profile'
    )

    # ── CORE REQUIRED FIELDS ──────────────────────────────────────────
    first_name      = models.CharField(max_length=100)
    last_name       = models.CharField(max_length=100)
    date_of_birth   = models.DateField()
    gender          = models.CharField(max_length=1, choices=GENDER_CHOICES)
    phone_number    = models.CharField(max_length=20)

    # ── Personal — optional, editable later ───────────────────────────
    middle_name     = models.CharField(max_length=100, blank=True)
    preferred_name  = models.CharField(max_length=100, blank=True,
        verbose_name="Preferred Name / Nickname")
    email           = models.EmailField(blank=True)
    marital_status  = models.CharField(max_length=10, choices=MARITAL_CHOICES, blank=True)
    religion        = models.CharField(max_length=15, choices=RELIGION_CHOICES, blank=True)
    occupation      = models.CharField(max_length=100, blank=True)
    alt_phone_number = models.CharField(max_length=20, blank=True,
        verbose_name="Alternative Phone Number")

    # ── Address — optional ────────────────────────────────────────────
    address         = models.TextField(blank=True, verbose_name="Current Address")
    city            = models.CharField(max_length=100, blank=True)
    state           = models.CharField(max_length=100, blank=True)
    hometown        = models.CharField(max_length=200, blank=True,
        verbose_name="Hometown / Village")
    state_of_origin = models.CharField(max_length=100, blank=True)
    nationality     = models.CharField(max_length=100, blank=True, default='Nigerian')
    lga             = models.CharField(max_length=100, blank=True,
        verbose_name="Local Government Area (LGA)")

    # ── Photo ─────────────────────────────────────────────────────────
    photo = models.ImageField(upload_to=patient_photo_upload_path, null=True, blank=True)

    # ── Medical — optional ────────────────────────────────────────────
    blood_group         = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True)
    genotype            = models.CharField(max_length=2, choices=GENOTYPE_CHOICES, blank=True)
    allergies           = models.TextField(blank=True)
    chronic_conditions  = models.TextField(blank=True)
    disabilities        = models.TextField(blank=True, verbose_name="Disabilities / Special Needs")
    primary_language    = models.CharField(max_length=100, blank=True,
        verbose_name="Primary Language")

    # ── Next of Kin ───────────────────────────────────────────────────
    nok_name         = models.CharField(max_length=200, blank=True,
        verbose_name="Next of Kin Full Name")
    nok_relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES, blank=True,
        verbose_name="Relationship to Patient")
    nok_phone        = models.CharField(max_length=20, blank=True,
        verbose_name="Next of Kin Phone")
    nok_alt_phone    = models.CharField(max_length=20, blank=True,
        verbose_name="Next of Kin Alt. Phone")
    nok_address      = models.TextField(blank=True,
        verbose_name="Next of Kin Address")
    nok_email        = models.EmailField(blank=True,
        verbose_name="Next of Kin Email")
    nok_occupation   = models.CharField(max_length=100, blank=True,
        verbose_name="Next of Kin Occupation")

    # ── Insurance — optional ──────────────────────────────────────────
    insurance_provider  = models.CharField(max_length=200, blank=True)
    insurance_number    = models.CharField(max_length=100, blank=True)
    nhis_number         = models.CharField(max_length=100, blank=True,
        verbose_name="NHIS Number")
    hmo_name            = models.CharField(max_length=200, blank=True,
        verbose_name="HMO Name")

    # ── Assignment ────────────────────────────────────────────────────
    assigned_doctor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_patients',
        limit_choices_to={'role': 'doctor'},
    )
    ward            = models.CharField(max_length=100, blank=True,
        verbose_name="Current Ward (if admitted)")

    # ── Import flag ───────────────────────────────────────────────────
    # True when the record was imported with PENDING dummy values
    # These fields are highlighted red in the patient preview
    has_pending_fields = models.BooleanField(default=False,
        help_text="True if any fields contain PENDING dummy data from import")
    pending_field_list = models.TextField(blank=True,
        help_text="Comma-separated list of fields that have PENDING values")

    # ── Status ────────────────────────────────────────────────────────
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)
    registered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='registered_patients',
    )

    # ── Computed properties ───────────────────────────────────────────
    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(p for p in parts if p).strip()

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = timezone.now().date()
        dob   = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def display_number(self):
        if self.legacy_hospital_number:
            return f"{self.hospital_number} (Old: {self.legacy_hospital_number})"
        return self.hospital_number

    @property
    def pending_fields(self):
        if self.pending_field_list:
            return [f.strip() for f in self.pending_field_list.split(',') if f.strip()]
        return []

    def __str__(self):
        return f"{self.full_name} [{self.hospital_number}]"

    class Meta:
        verbose_name        = "Patient"
        verbose_name_plural = "Patients"
        ordering = ['-created_at']
        indexes = [
            # These are the fields searched most often — indexes make them fast
            models.Index(fields=['hospital_number'],    name='idx_patient_hosp_num'),
            models.Index(fields=['last_name'],          name='idx_patient_last_name'),
            models.Index(fields=['phone_number'],       name='idx_patient_phone'),
            models.Index(fields=['is_active'],          name='idx_patient_active'),
            models.Index(fields=['assigned_doctor'],    name='idx_patient_doctor'),
            models.Index(fields=['created_at'],         name='idx_patient_created'),
            # Composite: active patients ordered by date (most common list query)
            models.Index(fields=['is_active', '-created_at'], name='idx_patient_active_date'),
        ]