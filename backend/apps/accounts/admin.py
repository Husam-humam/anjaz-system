from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'full_name', 'role', 'unit', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'full_name')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('المعلومات الشخصية', {'fields': ('full_name', 'role', 'unit')}),
        ('الصلاحيات', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'full_name', 'role', 'unit'),
        }),
    )
