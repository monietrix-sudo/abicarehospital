"""
AbiCare - Lab Results Models
==============================
Three ways to create lab templates:
1. Build from scratch (visual field builder)
2. Upload a PDF form — lab tech clicks to annotate (Canva-style)
3. Edit existing templates

LabResult stores either:
- result_values_json  (for scratch-built templates)
- pdf_annotations_json (for PDF-based templates — positions + values of text boxes)
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()


def lab_pdf_upload_path(instance, filename):
    """Store uploaded lab PDF templates in organized folder."""
    ext = filename.rsplit('.', 1)[-1].lower()
    return f"lab_templates/{timezone.now().strftime('%Y/%m')}/{instance.pk or 'new'}_{filename}"


class LabTemplate(models.Model):
    """
    Predefined lab test template.
    Can be scratch-built (fields_json) OR PDF-based (template_pdf).
    """

    CATEGORY_CHOICES = [
        ('haematology',   'Haematology'),
        ('biochemistry',  'Biochemistry'),
        ('microbiology',  'Microbiology'),
        ('immunology',    'Immunology'),
        ('urinalysis',    'Urinalysis'),
        ('radiology',     'Radiology'),
        ('other',         'Other'),
    ]

    TYPE_SCRATCH = 'scratch'
    TYPE_PDF     = 'pdf'
    TEMPLATE_TYPE_CHOICES = [
        (TYPE_SCRATCH, 'Built from Scratch'),
        (TYPE_PDF,     'Uploaded PDF Form'),
    ]

    name        = models.CharField(max_length=200, unique=True)
    category    = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='haematology')
    description = models.TextField(blank=True)
    template_type = models.CharField(
        max_length=10, choices=TEMPLATE_TYPE_CHOICES, default=TYPE_SCRATCH
    )

    # ── Scratch-built: JSON array of field definitions ────────────────
    # [{"name": "Haemoglobin", "unit": "g/dL", "normal_range": "12-17", "field_type": "number"}]
    fields_json = models.TextField(
        blank=True, default='[]',
        help_text="JSON array of fields (used for scratch-built templates)."
    )

    # ── PDF-based: uploaded blank form ────────────────────────────────
    template_pdf = models.FileField(
        upload_to='lab_templates/pdfs/',
        null=True, blank=True,
        help_text="Blank PDF form to annotate (used for PDF-based templates)."
    )

    is_active   = models.BooleanField(default=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    @property
    def fields(self):
        """Parse scratch fields as Python list."""
        try:
            return json.loads(self.fields_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def is_pdf_based(self):
        return self.template_type == self.TYPE_PDF

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    class Meta:
        verbose_name        = "Lab Template"
        verbose_name_plural = "Lab Templates"
        ordering = ['category', 'name']


class LabResult(models.Model):
    """
    Actual patient lab result — filled from either a scratch template
    or a PDF template with Canva-style click-to-annotate.
    """

    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('ready',      'Ready for Review'),
        ('released',   'Released'),
        ('amended',    'Amended'),
    ]

    patient     = models.ForeignKey(
        'patients.Patient', on_delete=models.CASCADE, related_name='lab_results'
    )
    template    = models.ForeignKey(
        LabTemplate, on_delete=models.SET_NULL, null=True, related_name='results'
    )
    appointment = models.ForeignKey(
        'appointments.Appointment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lab_results'
    )

    # ── Scratch-built result values ───────────────────────────────────
    # {"Haemoglobin": "14.2", "WBC": "6.8"}
    result_values_json = models.TextField(default='{}')

    # ── PDF annotation data ───────────────────────────────────────────
    # List of text box objects placed on the PDF:
    # [{"id":"tb1","page":1,"x":120,"y":340,"w":80,"h":24,"text":"14.2","fontSize":12,"color":"#000000"}]
    pdf_annotations_json = models.TextField(
        default='[]',
        help_text="JSON array of text annotations placed on the PDF form."
    )

    # Optional: rendered/filled PDF stored after annotation
    filled_pdf = models.FileField(
        upload_to='lab_results/filled_pdfs/',
        null=True, blank=True
    )

    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_date = models.DateField(default=timezone.now)
    notes       = models.TextField(blank=True)

    ordered_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     related_name='ordered_lab_results')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='processed_lab_results')
    released_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='released_lab_results')
    released_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    @property
    def result_values(self):
        try:
            return json.loads(self.result_values_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @result_values.setter
    def result_values(self, values_dict):
        self.result_values_json = json.dumps(values_dict)

    @property
    def pdf_annotations(self):
        try:
            return json.loads(self.pdf_annotations_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @pdf_annotations.setter
    def pdf_annotations(self, annotations_list):
        self.pdf_annotations_json = json.dumps(annotations_list)

    @property
    def is_visible_to_patient(self):
        return self.status == 'released'

    def __str__(self):
        name = self.template.name if self.template else 'Unknown Test'
        return f"{name} — {self.patient.hospital_number} ({self.result_date})"

    class Meta:
        verbose_name        = "Lab Result"
        verbose_name_plural = "Lab Results"
        ordering = ['-result_date', '-created_at']
