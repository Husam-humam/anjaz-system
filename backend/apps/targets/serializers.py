from rest_framework import serializers

from apps.indicators.models import Indicator

from .models import Target


class TargetIndicatorComponentSerializer(serializers.ModelSerializer):
    """تمثيل مُبسَّط لمؤشّر مكوّن داخل المستهدف."""
    category_name = serializers.CharField(
        source='category.name', read_only=True, allow_null=True,
    )

    class Meta:
        model = Indicator
        fields = [
            'id', 'name', 'unit_type', 'accumulation_type',
            'category', 'category_name',
        ]


class TargetSerializer(serializers.ModelSerializer):
    """مسلسل المستهدفات المركّبة الهرميّة (مؤسسة/دائرة/مديرية/قسم)"""

    scope_unit_name = serializers.CharField(
        source='scope_unit.name', read_only=True, default=None
    )
    scope_unit_type = serializers.CharField(
        source='scope_unit.unit_type', read_only=True, default=None
    )
    scope_level = serializers.CharField(read_only=True)

    # المؤشّرات (M2M): قراءة كقائمة مفصّلة + كتابة كقائمة معرّفات
    indicators = TargetIndicatorComponentSerializer(many=True, read_only=True)
    indicator_ids = serializers.PrimaryKeyRelatedField(
        queryset=Indicator.objects.all(),
        many=True,
        write_only=True,
        source='indicators',
        error_messages={
            'required': 'يجب اختيار مؤشّر واحد على الأقلّ',
            'empty': 'يجب اختيار مؤشّر واحد على الأقلّ',
        },
    )

    # وحدة المستهدف الموحّدة (مُشتقّة من أول مكوّن — كلها بنفس النوع بحكم القيد)
    unit_type = serializers.SerializerMethodField()

    set_by_name = serializers.CharField(
        source='set_by.full_name', read_only=True, default=None
    )
    # تقدّم — يُحسَب إذا طلبه المستدعي عبر context['with_progress']
    progress = serializers.SerializerMethodField()

    def get_unit_type(self, obj):
        first = obj.indicators.first()
        return first.unit_type if first else None

    def get_progress(self, obj):
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
            'id', 'name',
            'scope_unit', 'scope_unit_name', 'scope_unit_type', 'scope_level',
            'indicators', 'indicator_ids', 'unit_type',
            'year', 'target_value',
            'notes',
            'set_by', 'set_by_name',
            'created_at', 'updated_at',
            'progress',
        ]
        read_only_fields = ['set_by', 'created_at', 'updated_at']
        extra_kwargs = {
            'name': {
                'error_messages': {'required': 'اسم المستهدف مطلوب'},
            },
            'scope_unit': {
                'required': False,
                'allow_null': True,
                'error_messages': {
                    'does_not_exist': 'الوحدة التنظيمية المحدّدة غير موجودة',
                },
            },
            'year': {
                'error_messages': {'required': 'السنة مطلوبة'},
            },
            'target_value': {
                'error_messages': {'required': 'القيمة المستهدفة مطلوبة'},
            },
        }

    def validate(self, attrs):
        """
        التحقّق المسبق على الحقول الأساسيّة (name, year, scope, target_value).
        التحقّق من المكوّنات (unit_type متطابق، عدم تكرار اسم) يتمّ في الـ service
        لأنّه يحتاج indicators المرتبطة بالـ pk بعد الحفظ.
        """
        instance = self.instance or Target()
        for key, value in attrs.items():
            if key == 'indicators':
                # نتجاهل في clean — يُفحَص بعد الحفظ في validate_components
                continue
            setattr(instance, key, value)
        instance.clean()
        return attrs
