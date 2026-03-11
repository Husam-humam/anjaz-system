from django.core.exceptions import ValidationError

from .models import Target


class TargetService:

    @staticmethod
    def create_target(data, set_by):
        """إنشاء مستهدف جديد"""
        target = Target(**data)
        target.set_by = set_by
        target.full_clean()
        target.save()
        return target

    @staticmethod
    def update_target(target, data):
        """تحديث مستهدف"""
        for key, value in data.items():
            setattr(target, key, value)
        target.full_clean()
        target.save()
        return target

    @staticmethod
    def delete_target(target):
        """حذف مستهدف"""
        target.delete()

    @staticmethod
    def get_targets_for_qism(qism_id, year):
        """الحصول على مستهدفات قسم لسنة معينة"""
        return Target.objects.filter(
            qism_id=qism_id, year=year
        ).select_related('indicator', 'qism')
