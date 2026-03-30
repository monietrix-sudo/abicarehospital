"""
AbiCare - Clinical Records Models
====================================
Two record types:
1. PatientEncounter — inpatient (admission/ward/discharge) or outpatient visit
2. Diagnosis — tied to an encounter
3. Operation — tied to an encounter

Records are ALWAYS tied to a Patient.
Access: Doctor, Nurse, Admin can view.
Receptionist and Lab Tech get permission denied.
Patient can ONLY see records the doctor explicitly approves for them.
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class PatientEncounter(models.Model):
    """
    One clinical encounter — either inpatient admission or outpatient visit.
    Inpatient: has admission date, ward, discharge date.
    Outpatient: simpler — just date and consultation notes.
    """
    ENCOUNTER_TYPE_CHOICES = [
        ('inpatient',   'Inpatient Admission'),
        ('outpatient',  'Outpatient Visit'),
        ('emergency',   'Emergency'),
        ('day_case',    'Day Case / Day Surgery'),
        ('review',      'Follow-up Review'),
    ]
    WARD_CHOICES = [
        ('general_male',    'General Ward (Male)'),
        ('general_female',  'General Ward (Female)'),
        ('paediatric',      'Paediatric Ward'),
        ('maternity',       'Maternity Ward'),
        ('icu',             'ICU / Critical Care'),
        ('surgical',        'Surgical Ward'),
        ('medical',         'Medical Ward'),
        ('private',         'Private Ward'),
        ('semi_private',    'Semi-Private Ward'),
        ('emergency',       'Emergency Ward'),
        ('other',           'Other'),
    ]
    STATUS_CHOICES = [
        ('active',      'Active / Admitted'),
        ('discharged',  'Discharged'),
        ('transferred', 'Transferred'),
        ('deceased',    'Deceased'),
        ('outpatient',  'Outpatient — Completed'),
    ]

    patient          = models.ForeignKey(
        'patients.Patient', on_delete=models.CASCADE,
        related_name='encounters'
    )
    encounter_type   = models.CharField(
        max_length=20, choices=ENCOUNTER_TYPE_CHOICES, default='outpatient'
    )
    status           = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='outpatient'
    )

    # ── Dates ────────────────────────────────────────────────────────
    encounter_date   = models.DateField(default=timezone.now,
        verbose_name="Date of Visit / Admission")
    discharge_date   = models.DateField(null=True, blank=True,
        verbose_name="Date of Discharge")

    # ── Inpatient fields ──────────────────────────────────────────────
    ward_admitted    = models.CharField(
        max_length=30, choices=WARD_CHOICES, blank=True
    )
    bed_number       = models.CharField(max_length=20, blank=True)
    referring_doctor = models.CharField(max_length=200, blank=True,
        verbose_name="Referring Doctor / Facility")

    # ── Consultant ────────────────────────────────────────────────────
    consultant       = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='encounters_as_consultant',
        limit_choices_to={'role__in': ['doctor', 'admin']},
        verbose_name="Consultant / Doctor in Charge"
    )
    consultant_name_text = models.CharField(max_length=200, blank=True,
        verbose_name="Consultant (if not in system)")

    # ── Billing ───────────────────────────────────────────────────────
    billing_code     = models.CharField(max_length=100, blank=True,
        verbose_name="Billing / CPT Code")

    # ── Clinical notes ────────────────────────────────────────────────
    presenting_complaint = models.TextField(blank=True,
        verbose_name="Presenting Complaint / Reason for Visit")
    history_of_illness   = models.TextField(blank=True,
        verbose_name="History of Presenting Illness")
    examination_findings = models.TextField(blank=True,
        verbose_name="Examination Findings")
    treatment_plan       = models.TextField(blank=True,
        verbose_name="Treatment Plan / Management")
    discharge_summary    = models.TextField(blank=True)
    doctors_report       = models.TextField(blank=True,
        verbose_name="Doctor's Report / Clinical Notes")

    # ── Patient visibility ────────────────────────────────────────────
    # Doctor must explicitly approve before patient can see this record
    approved_for_patient = models.BooleanField(default=False,
        verbose_name="Approved for Patient Portal")
    approved_by          = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_encounters'
    )
    approved_at          = models.DateTimeField(null=True, blank=True)

    # ── Metadata ──────────────────────────────────────────────────────
    created_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_encounters'
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    @property
    def length_of_stay(self):
        """Auto-calculated from admission to discharge."""
        if self.encounter_type == 'inpatient' and self.encounter_date:
            end = self.discharge_date or timezone.now().date()
            return (end - self.encounter_date).days
        return None

    @property
    def consultant_display(self):
        if self.consultant:
            return f"Dr. {self.consultant.get_full_name()}"
        return self.consultant_name_text or "Not assigned"

    def __str__(self):
        return (
            f"{self.get_encounter_type_display()} — "
            f"{self.patient.full_name} on {self.encounter_date}"
        )

    class Meta:
        ordering = ['-encounter_date', '-created_at']
        verbose_name = "Patient Encounter"
        verbose_name_plural = "Patient Encounters"


class Diagnosis(models.Model):
    """
    One diagnosis tied to a patient encounter.
    Supports ICD-10 style codes (typed manually for now).
    """
    DIAGNOSIS_TYPE_CHOICES = [
        ('primary',       'Primary Diagnosis'),
        ('secondary',     'Secondary / Comorbidity'),
        ('differential',  'Differential Diagnosis'),
        ('provisional',   'Provisional / Working Diagnosis'),
        ('final',         'Final Diagnosis'),
        ('discharge',     'Discharge Diagnosis'),
    ]

    encounter        = models.ForeignKey(
        PatientEncounter, on_delete=models.CASCADE,
        related_name='diagnoses'
    )
    diagnosis_date   = models.DateField(default=timezone.now)
    diagnosis_code   = models.CharField(max_length=20, blank=True,
        verbose_name="ICD-10 Code",
        help_text="e.g. J18.9 for Pneumonia, I10 for Hypertension")
    diagnosis_name   = models.CharField(max_length=300,
        verbose_name="Diagnosis Name / Description")
    diagnosis_type   = models.CharField(
        max_length=20, choices=DIAGNOSIS_TYPE_CHOICES, default='primary'
    )
    notes            = models.TextField(blank=True,
        verbose_name="Diagnosis Notes / Doctor's Remarks")
    diagnosed_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='diagnoses_made'
    )
    created_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        code = f"[{self.diagnosis_code}] " if self.diagnosis_code else ""
        return f"{code}{self.diagnosis_name}"

    class Meta:
        ordering = ['-diagnosis_date']
        verbose_name = "Diagnosis"
        verbose_name_plural = "Diagnoses"


class Operation(models.Model):
    """
    A surgical or procedural operation tied to a patient encounter.
    """
    OPERATION_TYPE_CHOICES = [
        ('elective',    'Elective Surgery'),
        ('emergency',   'Emergency Surgery'),
        ('minor',       'Minor Procedure'),
        ('major',       'Major Surgery'),
        ('laparoscopic','Laparoscopic / Minimally Invasive'),
        ('diagnostic',  'Diagnostic Procedure'),
        ('therapeutic', 'Therapeutic Procedure'),
        ('other',       'Other'),
    ]
    OUTCOME_CHOICES = [
        ('successful',  'Successful'),
        ('complicated', 'Complicated'),
        ('failed',      'Failed / Abandoned'),
        ('pending',     'Pending / Scheduled'),
    ]

    encounter        = models.ForeignKey(
        PatientEncounter, on_delete=models.CASCADE,
        related_name='operations'
    )
    operation_date   = models.DateField(default=timezone.now)
    operation_type   = models.CharField(
        max_length=20, choices=OPERATION_TYPE_CHOICES, default='minor'
    )
    operation_name   = models.CharField(max_length=300,
        verbose_name="Name / Title of Operation")
    operation_code   = models.CharField(max_length=50, blank=True,
        verbose_name="Operation / CPT Code")
    anaesthesia_type = models.CharField(max_length=100, blank=True,
        verbose_name="Anaesthesia Type")
    duration_minutes = models.PositiveIntegerField(null=True, blank=True,
        verbose_name="Duration (minutes)")
    outcome          = models.CharField(
        max_length=20, choices=OUTCOME_CHOICES, default='successful'
    )
    surgeon          = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='operations_performed',
        verbose_name="Lead Surgeon"
    )
    surgeon_text     = models.CharField(max_length=200, blank=True,
        verbose_name="Lead Surgeon (if not in system)")
    notes            = models.TextField(blank=True,
        verbose_name="Operation Notes")
    doctors_remark   = models.TextField(blank=True,
        verbose_name="Doctor's Post-Op Remark")
    complications    = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.operation_name} on {self.operation_date}"

    class Meta:
        ordering = ['-operation_date']
        verbose_name = "Operation"
        verbose_name_plural = "Operations"

# Create your models here.
