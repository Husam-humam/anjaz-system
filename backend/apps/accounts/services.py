"""
طبقة الخدمات لتطبيق الحسابات — منطق الأعمال لإدارة المستخدمين.
"""
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services import AuditService

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

        # سجل التدقيق — قاعدة عمل #14
        AuditService.log(
            action_type=AuditLog.ActionType.USER_CREATED,
            actor=created_by,
            target=user,
            qism=user.unit if user.unit_id else None,
            metadata={
                'username': user.username,
                'role': user.role,
                'unit_id': user.unit_id,
            },
        )
        return user

    @staticmethod
    @transaction.atomic
    def update_user(user, data, actor=None):
        """تحديث بيانات مستخدم"""
        # نلتقط الحقول المُغيّرة لتسجيلها في الـ audit log
        changes = {}
        for key, value in data.items():
            if key != 'password':
                old = getattr(user, key, None)
                # نتجاهل تغيّر FK لـ unit بمقارنة الـ id
                old_repr = old.pk if hasattr(old, 'pk') else old
                new_repr = value.pk if hasattr(value, 'pk') else value
                if old_repr != new_repr:
                    changes[key] = {'old': old_repr, 'new': new_repr}
                setattr(user, key, value)
        user.full_clean()
        user.save()

        # سجل التدقيق — يميّز التعطيل/التفعيل كنوع منفصل لأهميّتها الأمنيّة
        if 'is_active' in changes:
            action_type = (
                AuditLog.ActionType.USER_REACTIVATED
                if changes['is_active']['new']
                else AuditLog.ActionType.USER_DEACTIVATED
            )
        else:
            action_type = AuditLog.ActionType.USER_UPDATED

        if actor is not None:
            AuditService.log(
                action_type=action_type,
                actor=actor,
                target=user,
                qism=user.unit if user.unit_id else None,
                metadata={
                    'username': user.username,
                    'changes': changes,
                },
            )
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
        # تغيير كلمة المرور الذاتيّة لا تُسجَّل في AuditLog لأنّها فعل المستخدم
        # على نفسه فقط — ليست حدثاً أمنياً يستدعي تتبّع الأدمن.
        return user

    @staticmethod
    @transaction.atomic
    def reset_password(user, new_password, actor=None):
        """إعادة تعيين كلمة المرور (يقوم بها الأدمن)"""
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            raise ValidationError({'password': e.messages})
        user.set_password(new_password)
        user.save(update_fields=['password'])
        logger.info(f"Password reset for user {user.username} (id={user.pk})")

        # إعادة التعيين من قِبَل الأدمن حدث أمني يُسجَّل دائماً
        if actor is not None:
            AuditService.log(
                action_type=AuditLog.ActionType.USER_PASSWORD_RESET,
                actor=actor,
                target=user,
                qism=user.unit if user.unit_id else None,
                metadata={'username': user.username},
            )
        return user
