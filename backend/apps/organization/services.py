from django.core.exceptions import ValidationError

from .models import OrganizationUnit


class OrganizationService:

    @staticmethod
    def create_unit(data, created_by=None):
        """إنشاء كيان تنظيمي جديد"""
        unit = OrganizationUnit(**data)
        unit.full_clean()
        unit.save()
        return unit

    @staticmethod
    def update_unit(unit, data):
        """تحديث كيان تنظيمي"""
        for key, value in data.items():
            setattr(unit, key, value)
        unit.full_clean()
        unit.save()
        return unit

    @staticmethod
    def deactivate_unit(unit):
        """تعطيل كيان تنظيمي (حذف ناعم)"""
        # التحقق من عدم وجود أقسام نشطة تحته
        active_children = unit.get_children().filter(is_active=True)
        if active_children.exists():
            raise ValidationError(
                'لا يمكن تعطيل كيان يحتوي على كيانات فرعية نشطة'
            )
        unit.is_active = False
        unit.save(update_fields=['is_active'])
        return unit

    @staticmethod
    def get_tree(user=None):
        """الحصول على شجرة الهيكل التنظيمي"""
        queryset = OrganizationUnit.objects.filter(is_active=True)
        if user and user.role != 'statistics_admin':
            queryset = queryset.for_user_scope(user)
        return queryset.filter(parent__isnull=True)
