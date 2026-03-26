"""AbiCare - Lab Results Admin."""
from django.contrib import admin
from django.utils.html import format_html
from .models import LabTemplate, LabResult


@admin.register(LabTemplate)
class LabTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active', 'created_by', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ['patient', 'template', 'result_date', 'status_badge', 'ordered_by', 'released_at']
    list_filter = ['status', 'result_date', 'template__category']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__hospital_number']
    readonly_fields = ['created_at', 'updated_at', 'released_at']

    def status_badge(self, obj):
        colors = {'pending': '#FFC107', 'processing': '#17A2B8', 'ready': '#0A5C8A',
                  'released': '#28A745', 'amended': '#E83E8C'}
        return format_html('<span style="background:{};color:white;padding:2px 8px;border-radius:10px;font-size:11px;">{}</span>',
                           colors.get(obj.status, '#6C757D'), obj.get_status_display())
    status_badge.short_description = 'Status'
