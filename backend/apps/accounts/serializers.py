"""
المسلسلات (Serializers) لتطبيق الحسابات — تحويل البيانات والتحقق من صحتها.
"""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.organization.serializers import OrganizationUnitSerializer

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    """مسلسل تسجيل الدخول"""
    username = serializers.CharField(
        required=True,
        error_messages={
            'required': 'اسم المستخدم مطلوب.',
            'blank': 'اسم المستخدم لا يمكن أن يكون فارغاً.',
        }
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        error_messages={
            'required': 'كلمة المرور مطلوبة.',
            'blank': 'كلمة المرور لا يمكن أن تكون فارغة.',
        }
    )


class TokenRefreshSerializer(serializers.Serializer):
    """مسلسل تحديث التوكن"""
    refresh = serializers.CharField(
        required=True,
        error_messages={
            'required': 'رمز التحديث مطلوب.',
            'blank': 'رمز التحديث لا يمكن أن يكون فارغاً.',
        }
    )


class UserProfileSerializer(serializers.ModelSerializer):
    """مسلسل الملف الشخصي للمستخدم (قراءة فقط)"""
    unit = OrganizationUnitSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'role', 'unit']
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    """مسلسل المستخدم — للقراءة"""
    unit_details = OrganizationUnitSerializer(source='unit', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'full_name', 'role',
            'unit', 'unit_details', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class UserCreateSerializer(serializers.ModelSerializer):
    """مسلسل إنشاء مستخدم جديد"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=6,
        error_messages={
            'required': 'كلمة المرور مطلوبة.',
            'blank': 'كلمة المرور لا يمكن أن تكون فارغة.',
            'min_length': 'كلمة المرور يجب أن تكون 6 أحرف على الأقل.',
        }
    )
    unit_details = OrganizationUnitSerializer(source='unit', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'password', 'full_name', 'role',
            'unit', 'unit_details', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'username': {
                'error_messages': {
                    'required': 'اسم المستخدم مطلوب.',
                    'blank': 'اسم المستخدم لا يمكن أن يكون فارغاً.',
                    'unique': 'اسم المستخدم مستخدم بالفعل.',
                }
            },
            'full_name': {
                'error_messages': {
                    'required': 'الاسم الكامل مطلوب.',
                    'blank': 'الاسم الكامل لا يمكن أن يكون فارغاً.',
                }
            },
            'role': {
                'error_messages': {
                    'required': 'الدور مطلوب.',
                    'invalid_choice': 'الدور المحدد غير صالح.',
                }
            },
        }

    def validate_username(self, value):
        """التحقق من عدم تكرار اسم المستخدم"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('اسم المستخدم مستخدم بالفعل.')
        return value


class UserUpdateSerializer(serializers.ModelSerializer):
    """مسلسل تحديث بيانات المستخدم (بدون كلمة المرور)"""
    unit_details = OrganizationUnitSerializer(source='unit', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'full_name', 'role',
            'unit', 'unit_details', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'username': {
                'error_messages': {
                    'required': 'اسم المستخدم مطلوب.',
                    'blank': 'اسم المستخدم لا يمكن أن يكون فارغاً.',
                    'unique': 'اسم المستخدم مستخدم بالفعل.',
                }
            },
            'full_name': {
                'error_messages': {
                    'required': 'الاسم الكامل مطلوب.',
                    'blank': 'الاسم الكامل لا يمكن أن يكون فارغاً.',
                }
            },
            'role': {
                'error_messages': {
                    'required': 'الدور مطلوب.',
                    'invalid_choice': 'الدور المحدد غير صالح.',
                }
            },
        }

    def validate_username(self, value):
        """التحقق من عدم تكرار اسم المستخدم (مع استثناء المستخدم الحالي)"""
        if User.objects.filter(username=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('اسم المستخدم مستخدم بالفعل.')
        return value


class ResetPasswordSerializer(serializers.Serializer):
    """مسلسل إعادة تعيين كلمة المرور"""
    new_password = serializers.CharField(
        required=True,
        min_length=6,
        write_only=True,
        error_messages={
            'required': 'كلمة المرور الجديدة مطلوبة.',
            'blank': 'كلمة المرور الجديدة لا يمكن أن تكون فارغة.',
            'min_length': 'كلمة المرور يجب أن تكون 6 أحرف على الأقل.',
        }
    )
