from rest_framework import serializers
from .models import OrganizationUnit


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
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at',
            'is_planning', 'is_supervised', 'external_id',
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
            'is_active', 'is_planning', 'is_supervised', 'children'
        ]

    def get_children(self, obj):
        children = obj.get_children().filter(is_active=True)
        return OrganizationTreeSerializer(children, many=True).data

    def get_is_planning(self, obj):
        return hasattr(obj, 'planning_assignment')

    def get_is_supervised(self, obj):
        return hasattr(obj, 'supervisor_link')
