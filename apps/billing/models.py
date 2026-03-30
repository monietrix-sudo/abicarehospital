"""
AbiCare - Billing Models
==========================
Flow:
1. Doctor creates Bill → assigns to patient encounter
2. Doctor sends to Nurse (status: sent_to_nurse)
3. Nurse reviews and sends to Patient Portal (status: sent_to_patient)
4. Patient pays online (Paystack) or cash (nurse records it)
5. Nurse confirms cash → notification to Doctor
6. Doctor confirms → sends success/failure/balance to Nurse
7. Nurse notifies Patient

Each step creates a notification and updates bill status.
"""

import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Bill(models.Model):
    STATUS_CHOICES = [
        ('draft',             'Draft — Not Sent'),
        ('sent_to_nurse',     'Sent to Nurse'),
        ('sent_to_patient',   'Sent to Patient'),
        ('partially_paid',    'Partially Paid'),
        ('paid',              'Fully Paid'),
        ('cancelled',         'Cancelled'),
        ('disputed',          'Disputed'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('paystack',  'Paystack — Card/Bank Transfer/USSD'),
        ('cash',      'Cash Payment'),
        ('bank_transfer', 'Direct Bank Transfer'),
        ('hmo',       'HMO / Insurance'),
        ('waived',    'Waived / Free'),
    ]

    bill_number  = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient      = models.ForeignKey(
        'patients.Patient', on_delete=models.CASCADE, related_name='bills'
    )
    encounter    = models.ForeignKey(
        'clinical_records.PatientEncounter', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='bills'
    )
    created_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_bills',
        verbose_name="Created by (Doctor/Admin)"
    )
    assigned_nurse = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_bills',
        limit_choices_to={'role': 'nurse'},
        verbose_name="Nurse in Charge"
    )

    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes          = models.TextField(blank=True, verbose_name="Doctor's billing notes")
    patient_message = models.TextField(blank=True,
        verbose_name="Message to patient about this bill")

    # Paystack
    paystack_reference = models.CharField(max_length=200, blank=True)
    paystack_verified  = models.BooleanField(default=False)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)
    sent_to_nurse_at   = models.DateTimeField(null=True, blank=True)
    sent_to_patient_at = models.DateTimeField(null=True, blank=True)
    paid_at            = models.DateTimeField(null=True, blank=True)

    @property
    def balance(self):
        return self.total_amount - self.amount_paid

    @property
    def is_fully_paid(self):
        return self.amount_paid >= self.total_amount

    @property
    def bill_number_short(self):
        return str(self.bill_number).upper()[:8]

    def __str__(self):
        return f"Bill #{self.bill_number_short} — {self.patient.full_name} — ₦{self.total_amount}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Bill"
        verbose_name_plural = "Bills"


class BillItem(models.Model):
    """One line item on a bill — e.g. Consultation, Lab Test, Drug, Ward."""
    ITEM_TYPE_CHOICES = [
        ('consultation', 'Consultation Fee'),
        ('procedure',    'Procedure / Operation'),
        ('laboratory',   'Laboratory Test'),
        ('radiology',    'Radiology / Imaging'),
        ('pharmacy',     'Pharmacy / Drugs'),
        ('ward',         'Ward / Accommodation'),
        ('nursing',      'Nursing Care'),
        ('other',        'Other'),
    ]
    bill        = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    item_type   = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    description = models.CharField(max_length=300)
    quantity    = models.PositiveIntegerField(default=1)
    unit_price  = models.DecimalField(max_digits=10, decimal_places=2)
    discount    = models.DecimalField(max_digits=5, decimal_places=2, default=0,
        verbose_name="Discount (₦)")

    @property
    def subtotal(self):
        return (self.unit_price * self.quantity) - self.discount

    def __str__(self):
        return f"{self.description} x{self.quantity} = ₦{self.subtotal}"

    class Meta:
        verbose_name = "Bill Item"


class Payment(models.Model):
    """Records one payment against a bill."""
    bill            = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments')
    amount          = models.DecimalField(max_digits=12, decimal_places=2)
    method          = models.CharField(max_length=20, choices=Bill.PAYMENT_METHOD_CHOICES)
    reference       = models.CharField(max_length=200, blank=True)
    recorded_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        verbose_name="Recorded by (Nurse/Admin)"
    )
    payment_date    = models.DateTimeField(default=timezone.now)
    notes           = models.TextField(blank=True)
    is_verified     = models.BooleanField(default=False)
    verified_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_payments'
    )

    def __str__(self):
        return f"Payment ₦{self.amount} for Bill #{self.bill.bill_number_short}"

    class Meta:
        ordering = ['-payment_date']
        verbose_name = "Payment"


class PaystackTransaction(models.Model):
    """Records every Paystack transaction attempt."""
    bill        = models.ForeignKey(Bill, on_delete=models.CASCADE,
                                    related_name='paystack_transactions')
    reference   = models.CharField(max_length=200, unique=True)
    amount      = models.DecimalField(max_digits=12, decimal_places=2)
    status      = models.CharField(max_length=20, default='pending')
    gateway_response = models.TextField(blank=True)
    paid_at     = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Paystack {self.reference} — {self.status}"

    class Meta:
        verbose_name = "Paystack Transaction"

# Create your models here.
