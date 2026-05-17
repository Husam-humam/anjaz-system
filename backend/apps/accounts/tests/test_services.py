"""
اختبارات طبقة الخدمات لتطبيق الحسابات — إدارة المستخدمين.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.accounts.services import UserService
from apps.accounts.tests.factories import (
    StatisticsAdminFactory,
    SectionManagerFactory,
)
from apps.organization.tests.factories import (
    QismFactory,
    PlanningQismFactory,
    StatisticsQismFactory,
)

User = get_user_model()


@pytest.mark.django_db
class TestUserServiceCreateUser:
    """اختبارات إنشاء مستخدم جديد"""

    def test_create_user_valid(self):
        """التحقق من إنشاء مستخدم جديد بنجاح مع بيانات صالحة"""
        admin = StatisticsAdminFactory()
        qism = QismFactory()

        data = {
            'username': 'new_user',
            'full_name': 'مستخدم جديد',
            'role': 'section_manager',
            'unit': qism,
            'password': 'securepass123',
        }
        user = UserService.create_user(data, created_by=admin)

        assert user.pk is not None
        assert user.username == 'new_user'
        assert user.full_name == 'مستخدم جديد'
        assert user.role == 'section_manager'
        assert user.unit == qism
        assert user.created_by == admin
        # التحقق من أن كلمة المرور مُشفرة وليست نصاً عادياً
        assert user.check_password('securepass123')
        assert user.password != 'securepass123'

    def test_create_user_statistics_admin_valid(self):
        """التحقق من إنشاء مدير إحصاء — بعد Phase F لا يحتاج إلى قسم إحصاء خاصّ."""
        admin = StatisticsAdminFactory()
        stats_qism = StatisticsQismFactory()

        data = {
            'username': 'new_stats_admin',
            'full_name': 'مدير إحصاء جديد',
            'role': 'statistics_admin',
            'unit': stats_qism,
            'password': 'securepass123',
        }
        user = UserService.create_user(data, created_by=admin)

        assert user.pk is not None
        assert user.role == 'statistics_admin'
        # بعد Phase F: لا يوجد qism_role — admin role لا يحتاج قسم خاصّ

    def test_create_user_without_unit_for_role_requiring_unit_fails(self):
        """مدير قسم بدون unit يجب أن يُرفض من قِبَل التحقّق في clean()."""
        admin = StatisticsAdminFactory()
        data = {
            'username': 'bad_manager_no_unit',
            'full_name': 'مدير بلا قسم',
            'role': 'section_manager',
            'unit': None,
            'password': 'securepass123',
        }
        with pytest.raises(ValidationError) as exc_info:
            UserService.create_user(data, created_by=admin)
        # إمّا 'unit' أو رسالة عربيّة تذكر «قسم»
        msg_dict = exc_info.value.message_dict
        assert 'unit' in msg_dict or any(
            'قسم' in str(v) for v in msg_dict.values()
        )


@pytest.mark.django_db
class TestUserServiceUpdateUser:
    """اختبارات تحديث بيانات المستخدم"""

    def test_update_user(self):
        """التحقق من تحديث بيانات المستخدم بنجاح"""
        user = SectionManagerFactory(full_name='اسم قديم')

        updated_user = UserService.update_user(user, {'full_name': 'اسم جديد'})

        assert updated_user.full_name == 'اسم جديد'
        user.refresh_from_db()
        assert user.full_name == 'اسم جديد'

    def test_update_user_ignores_password_field(self):
        """التحقق من أن التحديث يتجاهل حقل كلمة المرور"""
        user = SectionManagerFactory()
        old_password_hash = user.password

        UserService.update_user(user, {
            'full_name': 'اسم محدث',
            'password': 'should_be_ignored',
        })

        user.refresh_from_db()
        assert user.full_name == 'اسم محدث'
        # كلمة المرور يجب ألا تتغير
        assert user.password == old_password_hash

    def test_update_user_username(self):
        """التحقق من تحديث اسم المستخدم"""
        user = SectionManagerFactory(username='old_username')

        UserService.update_user(user, {'username': 'new_username'})

        user.refresh_from_db()
        assert user.username == 'new_username'


@pytest.mark.django_db
class TestUserServiceResetPassword:
    """اختبارات إعادة تعيين كلمة المرور"""

    def test_reset_password(self):
        """التحقق من إعادة تعيين كلمة المرور بنجاح"""
        user = SectionManagerFactory()
        assert user.check_password('password123')

        UserService.reset_password(user, 'newpassword456')

        user.refresh_from_db()
        assert user.check_password('newpassword456')
        assert not user.check_password('password123')

    def test_reset_password_returns_user(self):
        """التحقق من أن الدالة تُرجع كائن المستخدم"""
        user = SectionManagerFactory()

        result = UserService.reset_password(user, 'anotherpass789')

        assert result.pk == user.pk
