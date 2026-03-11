from rest_framework import serializers
from .models import OrganizationUnit


class OrganizationUnitSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True, default=None)

    class Meta:
        model = OrganizationUnit
        fields = [
            'id', 'name', 'code', 'unit_type', 'qism_role',
            'parent', 'parent_name', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        # إنشاء instance مؤقت للتحقق من الصحة
        instance = self.instance or OrganizationUnit()
        for key, value in attrs.items():
            setattr(instance, key, value)
        instance.clean()
        return attrs


class OrganizationTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationUnit
        fields = [
            'id', 'name', 'code', 'unit_type', 'qism_role',
            'is_active', 'children'
        ]

    def get_children(self, obj):
        children = obj.get_children().filter(is_active=True)
        return OrganizationTreeSerializer(children, many=True).data
