from rest_framework import serializers

from .models import (
    ExternalUnitTypeMapping,
    OrganizationUnit,
    PlanningAssignment,
    SupervisedUnit,
    ViewScope,
)


class OrganizationUnitSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True, default=None)
    # دور القسم مُشتقّ ديناميكياً من التخصيصات (لا حقل محلي)
    is_planning = serializers.SerializerMethodField()
    is_supervised = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationUnit
        fields = [
            'id', 'name', 'code', 'unit_type',
            'parent', 'parent_name', 'is_active',
            'is_planning', 'is_supervised', 'external_id',
            'employees_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at',
            'is_planning', 'is_supervised', 'external_id',
            'employees_count',
        ]

    def get_is_planning(self, obj):
        """قسم تخطيط = له PlanningAssignment."""
        return hasattr(obj, 'planning_assignment')

    def get_is_supervised(self, obj):
        """قسم مُشرَف عليه = له SupervisedUnit."""
        return hasattr(obj, 'supervisor_link')

    def validate(self, attrs):
        # إنشاء instance مؤقت للتحقق من الصحة
        instance = self.instance or OrganizationUnit()
        for key, value in attrs.items():
            setattr(instance, key, value)
        instance.clean()
        return attrs


class OrganizationTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    is_planning = serializers.SerializerMethodField()
    is_supervised = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationUnit
        fields = [
            'id', 'name', 'code', 'unit_type',
            'is_active', 'is_planning', 'is_supervised',
            'employees_count', 'children'
        ]

    def get_children(self, obj):
        children = obj.get_children().filter(is_active=True)
        return OrganizationTreeSerializer(children, many=True).data

    def get_is_planning(self, obj):
        return hasattr(obj, 'planning_assignment')

    def get_is_supervised(self, obj):
        return hasattr(obj, 'supervisor_link')


# ═══════════════════════════════════════════════════════════════
# Serializers لتخصيصات التخطيط و نطاقات الاطّلاع
# ═══════════════════════════════════════════════════════════════

class SupervisedUnitNestedSerializer(serializers.ModelSerializer):
    """قسم مُشرَف عليه — تمثيل مُبسَّط داخل PlanningAssignment."""
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    unit_code = serializers.CharField(source='unit.code', read_only=True)
    unit_employees_count = serializers.IntegerField(
        source='unit.employees_count', read_only=True,
    )

    class Meta:
        model = SupervisedUnit
        fields = [
            'id', 'unit', 'unit_name', 'unit_code',
            'unit_employees_count', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class PlanningAssignmentSerializer(serializers.ModelSerializer):
    """قراءة تخصيص قسم تخطيط مع الأقسام المُشرَف عليها."""
    planning_unit_name = serializers.CharField(source='planning_unit.name', read_only=True)
    planning_unit_code = serializers.CharField(source='planning_unit.code', read_only=True)
    context_parent_name = serializers.CharField(
        source='context_parent.name', read_only=True, default=None,
    )
    supervised_units = SupervisedUnitNestedSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True, default=None,
    )

    class Meta:
        model = PlanningAssignment
        fields = [
            'id', 'planning_unit', 'planning_unit_name', 'planning_unit_code',
            'context_parent', 'context_parent_name',
            'supervised_units', 'notes',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class PlanningAssignmentWriteSerializer(serializers.ModelSerializer):
    """كتابة تخصيص قسم تخطيط (إنشاء/تعديل)."""

    class Meta:
        model = PlanningAssignment
        fields = ['planning_unit', 'context_parent', 'notes']

    def validate_planning_unit(self, value):
        # عند الإنشاء: نمنع تكرار التخصيص (OneToOne على مستوى الـ DB لكن نُعطي
        # رسالة عربيّة أوضح).
        if self.instance is None and hasattr(value, 'planning_assignment'):
            raise serializers.ValidationError(
                'هذه الوحدة لديها تخصيص قسم تخطيط بالفعل.'
            )
        return value


class ViewScopeSerializer(serializers.ModelSerializer):
    """قراءة نطاق اطّلاع مع تفاصيل المستخدم والوحدات."""
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)
    viewable_units_detail = OrganizationUnitSerializer(
        source='viewable_units', many=True, read_only=True,
    )

    class Meta:
        model = ViewScope
        fields = [
            'id', 'user', 'user_full_name', 'user_role',
            'viewable_units', 'viewable_units_detail', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ViewScopeWriteSerializer(serializers.ModelSerializer):
    """كتابة نطاق اطّلاع — يدعم upsert (user OneToOne)."""

    class Meta:
        model = ViewScope
        fields = ['user', 'viewable_units', 'notes']


class ExternalUnitTypeMappingSerializer(serializers.ModelSerializer):
    """قراءة/كتابة تطابق نوع الوحدة الخارجي."""
    treat_as_display = serializers.CharField(
        source='get_treat_as_display', read_only=True, default=None,
    )

    class Meta:
        model = ExternalUnitTypeMapping
        fields = [
            'id', 'external_type_name', 'external_type_id',
            'treat_as', 'treat_as_display',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'external_type_name', 'external_type_id',
            'created_at', 'updated_at',
        ]

    def validate_treat_as(self, value):
        # السماح بـ None / 'daira' / 'mudiriya' / 'qism' / 'ignore'
        if value in ('', None):
            return None
        allowed = {choice[0] for choice in ExternalUnitTypeMapping.TreatAs.choices}
        if value not in allowed:
            raise serializers.ValidationError(
                f'القيمة يجب أن تكون إحدى: {", ".join(allowed)}'
            )
        return value
