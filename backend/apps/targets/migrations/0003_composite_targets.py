"""
ترحيل: تحويل المستهدفات إلى نموذج مركّب (M2M مع المؤشّرات + اسم وصفي).

⚠️ ترحيل مُدمِّر: يحذف كل المستهدفات الحاليّة لأن البيانات تجريبيّة
ولا تستحقّ تعقيد ترحيل تلقائي.
"""
from django.db import migrations, models


def delete_existing_targets(apps, schema_editor):
    Target = apps.get_model('targets', 'Target')
    Target.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('targets', '0002_scope_unit_rename'),
        ('indicators', '0001_initial'),
    ]

    operations = [
        # 1) حذف البيانات الحاليّة (تجريبيّة فقط)
        migrations.RunPython(
            delete_existing_targets,
            reverse_code=migrations.RunPython.noop,
        ),

        # 2) إزالة القيد الفريد القديم على (scope_unit, indicator, year)
        migrations.AlterUniqueTogether(
            name='target',
            unique_together=set(),
        ),

        # 3) إزالة فهارس متعلّقة بـ indicator FK
        migrations.RemoveIndex(
            model_name='target',
            name='idx_target_scope_ind_year',
        ),
        migrations.RemoveIndex(
            model_name='target',
            name='idx_target_indicator_year',
        ),

        # 4) إزالة الـ FK القديم
        migrations.RemoveField(
            model_name='target',
            name='indicator',
        ),

        # 5) إضافة حقل الاسم
        migrations.AddField(
            model_name='target',
            name='name',
            field=models.CharField(
                default='',
                max_length=200,
                help_text=(
                    'وصف مختصر للمستهدف (مثل «إعداد التقارير»). يُعرض في التقارير '
                    'كعنوان رئيسي مع تفصيل المكوّنات تحته.'
                ),
                verbose_name='اسم المستهدف',
            ),
            preserve_default=False,
        ),

        # 6) إضافة علاقة M2M للمؤشّرات
        migrations.AddField(
            model_name='target',
            name='indicators',
            field=models.ManyToManyField(
                related_name='targets',
                to='indicators.indicator',
                help_text=(
                    'المؤشّر/المؤشّرات التي يتركّب منها المستهدف. كل المكوّنات '
                    'يجب أن تكون بنفس نوع الوحدة (عدد، نسبة، إلخ).'
                ),
                verbose_name='المؤشّرات المُكوِّنة',
            ),
        ),

        # 7) فهرس جديد (scope + year) — لا فهرس على indicator بعد الآن
        migrations.AddIndex(
            model_name='target',
            index=models.Index(
                fields=['scope_unit', 'year'],
                name='idx_target_scope_year',
            ),
        ),
    ]
