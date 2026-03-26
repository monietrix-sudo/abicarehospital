"""AbiCare - Medications Admin."""
from django.contrib import admin
from .models import MedicationSchedule, MedicationDose


class MedicationDoseInline(admin.TabularInline):
    """Show doses inline inside the schedule admin."""
    model = MedicationDose
    extra = 0
    readonly_fields = ['taken_at']
    fields = ['scheduled_datetime', 'taken', 'taken_at', 'notes']


@admin.register(MedicationSchedule)
class MedicationScheduleAdmin(admin.ModelAdmin):
    list_display = ['drug_name', 'dosage', 'patient', 'prescribed_by', 'frequency',
                    'start_date', 'end_date', 'is_active']
    list_filter = ['frequency', 'route', 'is_active', 'prescribed_by']
    search_fields = ['drug_name', 'patient__first_name', 'patient__last_name', 'patient__hospital_number']
    readonly_fields = ['created_at']
    inlines = [MedicationDoseInline]


@admin.register(MedicationDose)
class MedicationDoseAdmin(admin.ModelAdmin):
    list_display = ['schedule', 'scheduled_datetime', 'taken', 'taken_at']
    list_filter = ['taken', 'scheduled_datetime']
    readonly_fields = ['taken_at']
