from rest_framework import serializers

from .models import Target


class TargetSerializer(serializers.ModelSerializer):
    qism_name = serializers.CharField(source='qism.name', read_only=True)
    indicator_name = serializers.CharField(source='indicator.name', read_only=True)

    class Meta:
        model = Target
        fields = [
            'id', 'qism', 'qism_name', 'indicator', 'indicator_name',
            'year', 'target_value', 'set_by', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['set_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        instance = self.instance or Target()
        for key, value in attrs.items():
            setattr(instance, key, value)
        instance.clean()
        return attrs
