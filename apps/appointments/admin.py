"""AbiCare - Appointments Admin."""
from django.contrib import admin
from django.utils.html import format_html
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = [
        'patient', 'doctor', 'appointment_date', 'appointment_time',
        'type_badge', 'status_badge', 'teleconsult_status'
    ]
    list_filter = ['status', 'appointment_type', 'appointment_date', 'doctor']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__hospital_number', 'doctor__first_name']
    readonly_fields = ['created_at', 'updated_at', 'teleconsult_approved_at']
    date_hierarchy = 'appointment_date'
    ordering = ['-appointment_date', '-appointment_time']

    fieldsets = (
        ('Appointment Info', {
            'fields': ('patient', 'doctor', 'appointment_date', 'appointment_time', 'duration_minutes', 'appointment_type', 'status'),
        }),
        ('Details', {
            'fields': ('reason', 'notes'),
        }),
        ('Teleconsultation', {
            'fields': ('teleconsult_link', 'teleconsult_approved', 'teleconsult_approved_by', 'teleconsult_approved_at', 'allow_recording'),
        }),
        ('Meta', {
            'fields': ('booked_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {'scheduled': '#17A2B8', 'confirmed': '#0A5C8A', 'in_progress': '#FFC107',
                  'completed': '#28A745', 'cancelled': '#DC3545', 'no_show': '#6C757D'}
        return format_html('<span style="background:{};color:white;padding:2px 8px;border-radius:10px;font-size:11px;">{}</span>',
                           colors.get(obj.status, '#6C757D'), obj.get_status_display())
    status_badge.short_description = 'Status'

    def type_badge(self, obj):
        color = '#E83E8C' if obj.appointment_type == 'teleconsult' else '#6C757D'
        return format_html('<span style="background:{};color:white;padding:2px 8px;border-radius:10px;font-size:11px;">{}</span>',
                           color, obj.get_appointment_type_display())
    type_badge.short_description = 'Type'

    def teleconsult_status(self, obj):
        if obj.appointment_type != 'teleconsult':
            return '—'
        if obj.teleconsult_approved:
            return format_html('<span style="color:#28A745;font-weight:bold;">✔ Approved</span>')
        return format_html('<span style="color:#DC3545;">✖ Pending</span>')
    teleconsult_status.short_description = 'Teleconsult'
