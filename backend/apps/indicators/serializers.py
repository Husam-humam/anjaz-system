from rest_framework import serializers

from .models import Indicator, IndicatorCategory


class IndicatorCategorySerializer(serializers.ModelSerializer):
    """مسلسل تصنيفات المؤشرات"""

    class Meta:
        model = IndicatorCategory
        fields = ['id', 'name', 'is_active']


class IndicatorSerializer(serializers.ModelSerializer):
    """مسلسل المؤشرات"""
    category_name = serializers.CharField(
        source='category.name', read_only=True, default=None
    )
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True, default=None
    )

    class Meta:
        model = Indicator
        fields = [
            'id', 'name', 'description', 'unit_type', 'unit_label',
            'accumulation_type', 'category', 'category_name',
            'is_active', 'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        """التحقق من صحة البيانات باستخدام قواعد النموذج"""
        instance = self.instance or Indicator()
        for key, value in attrs.items():
            setattr(instance, key, value)
        instance.clean()
        return attrs
