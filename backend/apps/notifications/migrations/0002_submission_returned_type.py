"""
إضافة نوع إشعار "إرجاع المنجز للتصحيح".
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("period_opened", "فتح أسبوع جديد"),
                    ("submission_due", "اقتراب الموعد النهائي"),
                    ("submission_late", "تأخر في التسليم"),
                    ("extension_granted", "منح تمديد"),
                    ("form_pending_approval", "استمارة بانتظار الاعتماد"),
                    ("form_approved", "اعتماد الاستمارة"),
                    ("form_rejected", "رفض الاستمارة"),
                    ("submission_received", "استلام منجز"),
                    ("submission_approved", "اعتماد المنجز"),
                    ("submission_returned", "إرجاع المنجز للتصحيح"),
                    ("qualitative_pending", "منجز نوعي بانتظار الاعتماد"),
                    ("qualitative_approved", "اعتماد المنجز النوعي"),
                    ("qualitative_rejected", "رفض المنجز النوعي"),
                ],
                max_length=30,
                verbose_name="نوع الإشعار",
            ),
        ),
    ]
