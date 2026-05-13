"""
Data migration: اعتبار كل المنجزات المعتمَدة حالياً كـ «مُراجَعة ضمنياً
من الإحصاء» عند إطلاق ميزة مراجعة الإحصاء.

السبب: النظام في بيئة التطوير ولا توجد بيانات تاريخية حقيقية يجب
إظهارها في قائمة «بانتظار مراجعة الإحصاء». اعتبارها كلّها مُراجَعة يُبسّط
إطلاق الميزة ويُجنّب إغراق صفحة الإحصاء بآلاف العناصر.

إن تغيّر هذا القرار لاحقاً، يكفي إنشاء data migration عكسية.
"""
from django.db import migrations
from django.utils import timezone


def grandfather_approved_submissions(apps, schema_editor):
    WeeklySubmission = apps.get_model('submissions', 'WeeklySubmission')
    now = timezone.now()
    WeeklySubmission.objects.filter(
        status='approved',
        admin_reviewed_at__isnull=True,
    ).update(
        admin_reviewed_at=now,
        admin_review_action='approved',
    )


def reverse_grandfather(apps, schema_editor):
    # العكس: مسح أختام المراجعة التي أضفناها
    WeeklySubmission = apps.get_model('submissions', 'WeeklySubmission')
    WeeklySubmission.objects.filter(
        admin_review_action='approved',
        admin_reviewed_by__isnull=True,
    ).update(
        admin_reviewed_at=None,
        admin_review_action='',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('submissions', '0004_weeklysubmission_admin_review_action_and_more'),
    ]

    operations = [
        migrations.RunPython(
            grandfather_approved_submissions,
            reverse_grandfather,
        ),
    ]
