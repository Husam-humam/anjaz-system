"""
الترحيل إلى نظام المستهدفات الهرمي:
- إعادة تسمية qism -> scope_unit (حفظ البيانات الموجودة)
- جعل scope_unit قابلاً لـ NULL (للدلالة على مستهدف على مستوى المؤسسة)
- تحديث الفهارس والقيد الفريد
"""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("targets", "0001_initial"),
        ("organization", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1) إزالة القيد الفريد والفهرس القديم قبل إعادة التسمية
        migrations.AlterUniqueTogether(
            name="target",
            unique_together=set(),
        ),
        migrations.RemoveIndex(
            model_name="target",
            name="idx_target_qism_ind_year",
        ),
        # 2) إعادة تسمية الحقل (يحفظ البيانات في قاعدة البيانات)
        migrations.RenameField(
            model_name="target",
            old_name="qism",
            new_name="scope_unit",
        ),
        # 3) جعل scope_unit قابلاً لـ NULL
        migrations.AlterField(
            model_name="target",
            name="scope_unit",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "الوحدة التنظيمية التي يخصّها المستهدف (دائرة/مديرية/قسم). "
                    "اترك فارغاً لإنشاء مستهدف على مستوى المؤسسة كاملة."
                ),
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="targets",
                to="organization.organizationunit",
                verbose_name="نطاق المستهدف",
            ),
        ),
        # 4) تحديث حقل set_by ليصبح blank=True (لدعم الإنشاء الآلي)
        migrations.AlterField(
            model_name="target",
            name="set_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="set_targets",
                to=settings.AUTH_USER_MODEL,
                verbose_name="حُدد بواسطة",
            ),
        ),
        # 5) إضافة القيد الفريد الجديد والفهارس
        migrations.AlterUniqueTogether(
            name="target",
            unique_together={("scope_unit", "indicator", "year")},
        ),
        migrations.AddIndex(
            model_name="target",
            index=models.Index(
                fields=["scope_unit", "indicator", "year"],
                name="idx_target_scope_ind_year",
            ),
        ),
        migrations.AddIndex(
            model_name="target",
            index=models.Index(
                fields=["indicator", "year"],
                name="idx_target_indicator_year",
            ),
        ),
    ]
