"""
طبقة الخدمات لتطبيق الحسابات — منطق الأعمال لإدارة المستخدمين.
"""
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

logger = logging.getLogger(__name__)

User = get_user_model()


class UserService:

    @staticmethod
    @transaction.atomic
    def create_user(data, created_by):
        """إنشاء مستخدم جديد"""
        password = data.pop('password')
        try:
            validate_password(password)
        except ValidationError as e:
            raise ValidationError({'password': e.messages})
        user = User(**data)
        user.created_by = created_by
        user.full_clean()
        user.set_password(password)
        user.save()
        return user

    @staticmethod
    @transaction.atomic
    def update_user(user, data):
        """تحديث بيانات مستخدم"""
        for key, value in data.items():
            if key != 'password':
                setattr(user, key, value)
        user.full_clean()
        user.save()
        return user

    @staticmethod
    @transaction.atomic
    def change_password(user, old_password, new_password):
        """تغيير كلمة المرور — يتحقق من كلمة المرور الحالية أولاً"""
        if not user.check_password(old_password):
            raise ValidationError({'old_password': ['كلمة المرور الحالية غير صحيحة.']})
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            raise ValidationError({'new_password': e.messages})
        user.set_password(new_password)
        user.save(update_fields=['password'])
        logger.info(f"Password changed by user {user.username} (id={user.pk})")
        return user

    @staticmethod
    @transaction.atomic
    def reset_password(user, new_password):
        """إعادة تعيين كلمة المرور"""
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            raise ValidationError({'password': e.messages})
        user.set_password(new_password)
        user.save(update_fields=['password'])
        # إشعار بتغيير كلمة المرور
        logger.info(f"Password reset for user {user.username} (id={user.pk})")
        return user
