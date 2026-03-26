"""
AbiCare - Patients Admin
=========================
Full patient management: add, remove, assign doctor, view history.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = [
        'photo_thumb', 'hospital_number', 'full_name',
        'age', 'gender', 'blood_group', 'assigned_doctor',
        'phone_number', 'is_active', 'created_at'
    ]
    list_display_links = ['hospital_number', 'full_name']
    list_filter = ['gender', 'blood_group', 'genotype', 'is_active', 'assigned_doctor']
    search_fields = [
        'hospital_number', 'first_name', 'last_name',
        'middle_name', 'phone_number', 'email'
    ]
    readonly_fields = ['patient_id', 'created_at', 'updated_at', 'age_display']
    ordering = ['-created_at']
    list_per_page = 30

    fieldsets = (
        ('Identity', {
            'fields': ('patient_id', 'hospital_number', 'user_account', 'photo', 'age_display'),
        }),
        ('Personal Information', {
            'fields': (
                'first_name', 'middle_name', 'last_name',
                'date_of_birth', 'gender', 'marital_status',
                'nationality', 'state_of_origin', 'religion', 'occupation',
            ),
        }),
        ('Contact Details', {
            'fields': ('phone_number', 'alt_phone_number', 'email', 'address', 'city', 'state'),
        }),
        ('Medical Information', {
            'fields': ('blood_group', 'genotype', 'allergies', 'chronic_conditions'),
        }),
        ('Next of Kin', {
            'fields': ('nok_name', 'nok_relationship', 'nok_phone', 'nok_address'),
            'classes': ('collapse',),
        }),
        ('Hospital Assignment', {
            'fields': ('assigned_doctor', 'is_active', 'registered_by'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def photo_thumb(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;border:2px solid #0A5C8A;" />',
                obj.photo.url
            )
        initials = (obj.first_name[:1] + obj.last_name[:1]).upper()
        return format_html(
            '<div style="width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#0A5C8A,#00C49A);'
            'color:white;display:flex;align-items:center;justify-content:center;font-weight:bold;">{}</div>',
            initials
        )
    photo_thumb.short_description = ''

    def age_display(self, obj):
        return f"{obj.age} years"
    age_display.short_description = "Age"

    actions = ['activate_patients', 'deactivate_patients']

    def activate_patients(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} patients activated.")
    activate_patients.short_description = "Activate selected patients"

    def deactivate_patients(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} patients deactivated.")
    deactivate_patients.short_description = "Deactivate selected patients"
