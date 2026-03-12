from rest_framework import serializers

from apps.indicators.models import Indicator
from apps.organization.models import OrganizationUnit
from .models import FormTemplate, FormTemplateItem


class FormTemplateItemSerializer(serializers.ModelSerializer):
    """مسلسل بنود قالب الاستمارة"""
    indicator_name = serializers.CharField(
        source='indicator.name', read_only=True
    )
    indicator_unit_type = serializers.CharField(
        source='indicator.unit_type', read_only=True
    )
    indicator_unit_label = serializers.CharField(
        source='indicator.unit_label', read_only=True
    )

    class Meta:
        model = FormTemplateItem
        fields = [
            'id', 'indicator', 'indicator_name',
            'indicator_unit_type', 'indicator_unit_label',
            'is_mandatory', 'display_order',
        ]


class FormTemplateSerializer(serializers.ModelSerializer):
    """مسلسل قالب الاستمارة — للقراءة"""
    items = FormTemplateItemSerializer(many=True, read_only=True)
    qism_name = serializers.CharField(
        source='qism.name', read_only=True
    )
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True, default=None
    )
    approved_by_name = serializers.CharField(
        source='approved_by.full_name', read_only=True, default=None
    )
    rejected_by_name = serializers.CharField(
        source='rejected_by.full_name', read_only=True, default=None
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )

    class Meta:
        model = FormTemplate
        fields = [
            'id', 'qism', 'qism_name', 'version', 'status', 'status_display',
            'effective_from_week', 'effective_from_year',
            'notes', 'rejection_reason',
            'created_by', 'created_by_name',
            'approved_by', 'approved_by_name',
            'rejected_by', 'rejected_by_name',
            'created_at', 'approved_at',
            'items',
        ]
        read_only_fields = [
            'id', 'version', 'status', 'effective_from_week',
            'effective_from_year', 'rejection_reason',
            'created_by', 'approved_by', 'rejected_by',
            'created_at', 'approved_at',
        ]


class FormTemplateItemCreateSerializer(serializers.Serializer):
    """مسلسل بند الاستمارة — للإنشاء والتحديث"""
    indicator = serializers.PrimaryKeyRelatedField(
        queryset=Indicator.objects.filter(is_active=True),
        error_messages={
            'does_not_exist': 'المؤشر المحدد غير موجود',
            'incorrect_type': 'قيمة غير صالحة لمعرف المؤشر',
        }
    )
    is_mandatory = serializers.BooleanField(default=False)
    display_order = serializers.IntegerField(default=0, min_value=0)


class FormTemplateCreateSerializer(serializers.Serializer):
    """مسلسل إنشاء قالب الاستمارة مع البنود"""
    qism = serializers.PrimaryKeyRelatedField(
        queryset=OrganizationUnit.objects.filter(
            unit_type='qism', qism_role='regular', is_active=True
        ),
        error_messages={
            'does_not_exist': 'القسم المحدد غير موجود',
            'incorrect_type': 'قيمة غير صالحة لمعرف القسم',
        }
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    items = FormTemplateItemCreateSerializer(many=True)

    def validate_items(self, value):
        """التحقق من وجود بنود"""
        if not value:
            raise serializers.ValidationError(
                'يجب أن تحتوي الاستمارة على بند واحد على الأقل'
            )

        # التحقق من عدم تكرار المؤشرات
        indicator_ids = [item['indicator'].pk for item in value]
        if len(indicator_ids) != len(set(indicator_ids)):
            raise serializers.ValidationError(
                'لا يمكن تكرار نفس المؤشر في الاستمارة'
            )

        return value


class FormTemplateUpdateSerializer(serializers.Serializer):
    """مسلسل تحديث قالب الاستمارة"""
    notes = serializers.CharField(required=False, allow_blank=True)
    items = FormTemplateItemCreateSerializer(many=True, required=False)

    def validate_items(self, value):
        """التحقق من وجود بنود عند التحديث"""
        if value is not None and not value:
            raise serializers.ValidationError(
                'يجب أن تحتوي الاستمارة على بند واحد على الأقل'
            )

        # التحقق من عدم تكرار المؤشرات
        if value:
            indicator_ids = [item['indicator'].pk for item in value]
            if len(indicator_ids) != len(set(indicator_ids)):
                raise serializers.ValidationError(
                    'لا يمكن تكرار نفس المؤشر في الاستمارة'
                )

        return value


class FormTemplateApproveSerializer(serializers.Serializer):
    """مسلسل اعتماد قالب الاستمارة"""
    effective_from_week = serializers.IntegerField(
        min_value=1, max_value=53,
        error_messages={
            'min_value': 'رقم الأسبوع يجب أن يكون 1 على الأقل',
            'max_value': 'رقم الأسبوع يجب ألا يتجاوز 53',
            'required': 'يجب تحديد الأسبوع الذي يسري منه القالب',
        }
    )
    effective_from_year = serializers.IntegerField(
        min_value=2020, max_value=2100,
        error_messages={
            'min_value': 'السنة يجب أن تكون 2020 على الأقل',
            'max_value': 'السنة يجب ألا تتجاوز 2100',
            'required': 'يجب تحديد السنة التي يسري منها القالب',
        }
    )


class FormTemplateRejectSerializer(serializers.Serializer):
    """مسلسل رفض قالب الاستمارة"""
    rejection_reason = serializers.CharField(
        min_length=1,
        error_messages={
            'required': 'يجب تحديد سبب الرفض',
            'blank': 'سبب الرفض لا يمكن أن يكون فارغاً',
            'min_length': 'يجب تحديد سبب الرفض',
        }
    )
