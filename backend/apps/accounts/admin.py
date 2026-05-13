from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserRole


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

    def has_add_permission(self, request):
        """
        قاعدة CLAUDE.md #9: فقط مدير قسم الإحصاء يُنشئ المستخدمين.
        نسمح للـ superuser كحل طارئ (first-time bootstrap) لكن نمنع باقي staff.
        """
        user = request.user
        if user.is_superuser:
            return True
        return bool(user.is_authenticated and user.role == UserRole.STATISTICS_ADMIN)

    def has_change_permission(self, request, obj=None):
        user = request.user
        if user.is_superuser:
            return True
        return bool(user.is_authenticated and user.role == UserRole.STATISTICS_ADMIN)

    def has_delete_permission(self, request, obj=None):
        user = request.user
        if user.is_superuser:
            return True
        return bool(user.is_authenticated and user.role == UserRole.STATISTICS_ADMIN)

    def save_model(self, request, obj, form, change):
        """استدعاء full_clean لفرض قواعد النموذج (تطابق الدور مع نوع الوحدة)."""
        obj.full_clean()
        super().save_model(request, obj, form, change)
