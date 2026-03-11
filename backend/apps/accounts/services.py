"""
طبقة الخدمات لتطبيق الحسابات — منطق الأعمال لإدارة المستخدمين.
"""
from django.contrib.auth import get_user_model

User = get_user_model()


class UserService:

    @staticmethod
    def create_user(data, created_by):
        """إنشاء مستخدم جديد"""
        password = data.pop('password')
        user = User(**data)
        user.created_by = created_by
        user.set_password(password)
        user.full_clean()
        user.save()
        return user

    @staticmethod
    def update_user(user, data):
        """تحديث بيانات مستخدم"""
        for key, value in data.items():
            if key != 'password':
                setattr(user, key, value)
        user.full_clean()
        user.save()
        return user

    @staticmethod
    def reset_password(user, new_password):
        """إعادة تعيين كلمة المرور"""
        user.set_password(new_password)
        user.save(update_fields=['password'])
        return user
