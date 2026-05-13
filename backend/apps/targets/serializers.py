from rest_framework import serializers

from apps.indicators.models import Indicator

from .models import Target


class TargetSerializer(serializers.ModelSerializer):
    """مسلسل المستهدفات الهرمية (مؤسسة/دائرة/مديرية/قسم)"""

    scope_unit_name = serializers.CharField(
        source='scope_unit.name', read_only=True, default=None
    )
    scope_unit_type = serializers.CharField(
        source='scope_unit.unit_type', read_only=True, default=None
    )
    scope_level = serializers.CharField(read_only=True)
    indicator_name = serializers.CharField(
        source='indicator.name', read_only=True
    )
    indicator_unit_type = serializers.CharField(
        source='indicator.unit_type', read_only=True
    )
    indicator_accumulation_type = serializers.CharField(
        source='indicator.accumulation_type', read_only=True
    )
    indicator_category = serializers.IntegerField(
        source='indicator.category_id', read_only=True, allow_null=True,
    )
    indicator_category_name = serializers.CharField(
        source='indicator.category.name', read_only=True, allow_null=True,
    )
    set_by_name = serializers.CharField(
        source='set_by.full_name', read_only=True, default=None
    )
    # حقل التقدم — يُحسب فقط إذا طلبه المستدعي عبر context['with_progress']
    progress = serializers.SerializerMethodField()

    def get_progress(self, obj):
        """
        يحسب التقدم (cumulative, percentage, ...) للمستهدف.
        يُفعَّل فقط إذا مرّر الـ view parameter with_progress في الـ context.
        """
        if not self.context.get('with_progress'):
            return None
        try:
            from .services import TargetService
            return TargetService.compute_target_progress(obj)
        except Exception:
            return None

    class Meta:
        model = Target
        fields = [
            'id',
            'scope_unit', 'scope_unit_name', 'scope_unit_type', 'scope_level',
            'indicator', 'indicator_name',
            'indicator_unit_type', 'indicator_accumulation_type',
            'indicator_category', 'indicator_category_name',
            'year', 'target_value',
            'notes',
            'set_by', 'set_by_name',
            'created_at', 'updated_at',
            'progress',
        ]
        read_only_fields = ['set_by', 'created_at', 'updated_at']
        extra_kwargs = {
            'scope_unit': {
                'required': False,
                'allow_null': True,
                'error_messages': {
                    'does_not_exist': 'الوحدة التنظيمية المحدّدة غير موجودة',
                },
            },
            'indicator': {
                'error_messages': {
                    'required': 'المؤشر مطلوب',
                    'does_not_exist': 'المؤشر المحدّد غير موجود',
                },
            },
            'year': {
                'error_messages': {
                    'required': 'السنة مطلوبة',
                },
            },
            'target_value': {
                'error_messages': {
                    'required': 'القيمة المستهدفة مطلوبة',
                },
            },
        }

    def validate(self, attrs):
        """التحقق من صحة بيانات المستهدف عبر استدعاء clean() في النموذج"""
        instance = self.instance or Target()
        for key, value in attrs.items():
            setattr(instance, key, value)
        instance.clean()
        return attrs
