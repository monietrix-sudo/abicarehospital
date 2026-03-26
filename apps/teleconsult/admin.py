"""AbiCare - Teleconsult Admin."""
from django.contrib import admin
from .models import ConsultLink

@admin.register(ConsultLink)
class ConsultLinkAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'platform', 'label', 'link', 'is_active', 'created_at']
    list_filter = ['platform', 'is_active', 'doctor']
    search_fields = ['doctor__first_name', 'doctor__last_name', 'label']
