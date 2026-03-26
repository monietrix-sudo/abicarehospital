"""
AbiCare - Accounts Admin
=========================
Custom admin for User model. Makes role assignment easy.
All role changes are logged via AuditLog automatically.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin view for hospital staff/patient accounts.
    Roles can be changed with a single dropdown here.
    """

    # ── List display columns ──────────────────────────────────────────────────
    list_display = [
        'avatar_preview', 'username', 'full_name_display',
        'role_badge', 'department', 'phone_number',
        'is_active', 'date_joined'
    ]
    list_display_links = ['username', 'full_name_display']
    list_filter = ['role', 'is_active', 'department', 'is_staff', 'is_superuser']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'phone_number']
    ordering = ['last_name', 'first_name']
    list_per_page = 25

    # ── Fieldsets for add/edit form ───────────────────────────────────────────
    fieldsets = (
        ('Account Credentials', {
            'fields': ('username', 'password'),
            'classes': ('wide',),
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone_number', 'profile_picture'),
        }),
        ('Hospital Role & Department', {
            'fields': ('role', 'department', 'license_number'),
            'description': 'Set the user role to control their access level.',
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )

    # Fieldsets for the "Add User" page
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'first_name', 'last_name', 'email',
                'phone_number', 'role', 'department',
                'password1', 'password2',
            ),
        }),
    )

    # ── Custom display methods ────────────────────────────────────────────────
    def avatar_preview(self, obj):
        """Show tiny avatar thumbnail in list view."""
        if obj.profile_picture:
            return format_html(
                '<img src="{}" style="width:36px;height:36px;border-radius:50%;object-fit:cover;" />',
                obj.profile_picture.url
            )
        # Default initials avatar
        initials = (obj.first_name[:1] + obj.last_name[:1]).upper() or obj.username[:2].upper()
        return format_html(
            '<div style="width:36px;height:36px;border-radius:50%;background:#0A5C8A;'
            'color:white;display:flex;align-items:center;justify-content:center;'
            'font-weight:bold;font-size:12px;">{}</div>',
            initials
        )
    avatar_preview.short_description = ''

    def full_name_display(self, obj):
        return obj.get_full_name() or '—'
    full_name_display.short_description = 'Full Name'

    def role_badge(self, obj):
        """Color-coded role badge."""
        colors = {
            'admin': '#DC3545',
            'doctor': '#0A5C8A',
            'nurse': '#00C49A',
            'lab_tech': '#FFC107',
            'receptionist': '#6C757D',
            'patient': '#17A2B8',
        }
        color = colors.get(obj.role, '#6C757D')
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_role_display()
        )
    role_badge.short_description = 'Role'

    # ── Quick actions ─────────────────────────────────────────────────────────
    actions = ['activate_users', 'deactivate_users']

    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} users activated.")
    activate_users.short_description = "Activate selected users"

    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} users deactivated.")
    deactivate_users.short_description = "Deactivate selected users"
