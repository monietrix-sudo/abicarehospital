"""
AbiCare - Excel Import / Export Models
========================================
Every import session is recorded here.
Rows that fail are saved as ImportError records so admin
can fix them manually later without re-running the whole import.
"""

from django.db import models


class ImportSession(models.Model):
    """One Excel file upload = one ImportSession."""
    STATUS_CHOICES = [
        ('processing',            'Processing'),
        ('complete',              'Complete'),
        ('complete_with_errors',  'Complete — Some Rows Had Errors'),
        ('failed',                'Failed'),
    ]

    uploaded_by   = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='import_sessions'
    )
    file_name     = models.CharField(max_length=300)
    uploaded_at   = models.DateTimeField(auto_now_add=True)
    status        = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default='processing'
    )
    total_rows    = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    error_count   = models.IntegerField(default=0)
    skip_count    = models.IntegerField(default=0)
    notes         = models.TextField(blank=True)

    class Meta:
        ordering     = ['-uploaded_at']
        verbose_name = 'Import Session'

    def __str__(self):
        return f"Import #{self.pk} — {self.file_name} ({self.get_status_display()})"


class ImportError(models.Model):
    """
    One row that could not be imported.
    Saved so admin or receptionist can fix it manually later.
    The rest of the import continues — one bad row never blocks the file.
    """
    ERROR_TYPE_CHOICES = [
        ('missing_required', 'Missing Required Field'),
        ('invalid_format',   'Invalid Data Format'),
        ('duplicate',        'Duplicate Patient'),
        ('conflict',         'Conflict with Existing Record'),
        ('other',            'Other Error'),
    ]

    session       = models.ForeignKey(
        ImportSession, on_delete=models.CASCADE, related_name='errors'
    )
    row_number    = models.IntegerField(help_text="Row number in the Excel file (row 1 = header)")
    error_type    = models.CharField(max_length=30, choices=ERROR_TYPE_CHOICES)
    field_name    = models.CharField(max_length=100, blank=True)
    error_message = models.TextField()
    raw_data      = models.JSONField(
        default=dict,
        help_text="The original row data that failed, saved for manual correction"
    )
    is_resolved   = models.BooleanField(default=False)
    resolved_at   = models.DateTimeField(null=True, blank=True)
    resolved_by   = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_import_errors'
    )

    class Meta:
        ordering     = ['row_number']
        verbose_name = 'Import Error'

    def __str__(self):
        return (
            f"Row {self.row_number} — "
            f"{self.get_error_type_display()}: "
            f"{self.error_message[:60]}"
        )

# Create your models here.
