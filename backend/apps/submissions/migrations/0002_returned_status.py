"""
إضافة حالة "مُرجَع للتصحيح" إلى WeeklySubmission.Status.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="weeklysubmission",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "مسودة"),
                    ("submitted", "مُرسل"),
                    ("approved", "معتمد"),
                    ("returned", "مُرجَع للتصحيح"),
                    ("late", "متأخر"),
                    ("extended", "مُمدَّد"),
                ],
                default="draft",
                max_length=15,
                verbose_name="الحالة",
            ),
        ),
    ]
