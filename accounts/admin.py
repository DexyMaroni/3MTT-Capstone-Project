from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'location', 'is_staff']
    list_filter = ['role', 'is_staff', 'is_active']
    # Reuse Django's fieldsets and append our extra columns.
    fieldsets = UserAdmin.fieldsets + (
        ('Marketplace', {'fields': ('role', 'phone', 'location')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Marketplace', {'fields': ('role', 'phone', 'location')}),
    )
