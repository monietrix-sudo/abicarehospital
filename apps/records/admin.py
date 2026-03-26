"""AbiCare - Records Admin."""
from django.contrib import admin
from django.utils.html import format_html
from .models import MedicalRecord


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ['title', 'patient', 'record_type', 'file_type_badge',
                    'is_visible_to_patient', 'uploaded_by', 'uploaded_at', 'is_deleted']
    list_filter = ['record_type', 'file_type', 'is_visible_to_patient', 'is_deleted']
    search_fields = ['title', 'patient__first_name', 'patient__last_name', 'patient__hospital_number']
    readonly_fields = ['uploaded_at', 'updated_at', 'deleted_at', 'file_type']

    def file_type_badge(self, obj):
        icons = {'image': '🖼', 'pdf': '📄', 'video': '🎬', 'document': '📝', '': '📋'}
        return icons.get(obj.file_type, '📋') + ' ' + obj.file_type.title() if obj.file_type else '—'
    file_type_badge.short_description = 'File Type'
