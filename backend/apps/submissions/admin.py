from django.contrib import admin
from django.urls import reverse
from django.shortcuts import redirect
from .models import (
    QismExtension,
    SubmissionAnswer,
    SystemConfiguration,
    WeeklyPeriod,
    WeeklySubmission,
)


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    """
    إدارة إعدادات النظام — Singleton.
    يُعرض تلقائياً كنموذج واحد فقط ولا يمكن إضافة/حذف سجلات.
    """
    fieldsets = (
        ('الإدارة التلقائية للأسابيع', {
            'fields': (
                'auto_create_enabled',
                'auto_close_previous',
                'week_start_day',
            ),
            'description': (
                'تحدّد هذه الإعدادات كيف يُدير النظام الأسابيع تلقائياً. '
                'عند التفعيل، يُنشئ النظام الأسبوع الحالي عند بدايته ويُغلق السابق بعد الموعد النهائي.'
            ),
        }),
        ('إعدادات الموعد النهائي', {
            'fields': (
                'deadline_days_after_week_end',
                'deadline_hour',
            ),
            'description': (
                'الموعد النهائي = تاريخ نهاية الأسبوع + عدد الأيام + الساعة المحدّدة. '
                'مثال: نهاية الأسبوع الجمعة + 3 أيام + الساعة 12 = الاثنين 12 ظهراً.'
            ),
        }),
        ('معلومات النظام', {
            'fields': ('updated_at',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        # السماح فقط إذا لم يكن هناك سجل بعد
        return not SystemConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """إعادة التوجيه مباشرة إلى صفحة التحرير للسجل الأحادي"""
        obj = SystemConfiguration.load()
        return redirect(
            reverse('admin:submissions_systemconfiguration_change', args=[obj.pk])
        )


@admin.register(WeeklyPeriod)
class WeeklyPeriodAdmin(admin.ModelAdmin):
    list_display = ('year', 'week_number', 'start_date', 'end_date', 'deadline', 'status')
    list_filter = ('status', 'year')
    search_fields = ('year',)


class SubmissionAnswerInline(admin.TabularInline):
    model = SubmissionAnswer
    extra = 0
    raw_id_fields = ('form_item', 'qualitative_approved_by')


@admin.register(WeeklySubmission)
class WeeklySubmissionAdmin(admin.ModelAdmin):
    list_display = ('qism', 'weekly_period', 'form_template', 'status', 'submitted_at')
    list_filter = ('status', 'weekly_period__year')
    search_fields = ('qism__name',)
    raw_id_fields = ('qism', 'weekly_period', 'form_template', 'planning_approved_by')
    inlines = [SubmissionAnswerInline]


@admin.register(SubmissionAnswer)
class SubmissionAnswerAdmin(admin.ModelAdmin):
    list_display = ('submission', 'form_item', 'numeric_value', 'is_qualitative', 'qualitative_status')
    list_filter = ('is_qualitative', 'qualitative_status')
    search_fields = ('submission__qism__name', 'form_item__indicator__name')
    raw_id_fields = ('submission', 'form_item', 'qualitative_approved_by')


@admin.register(QismExtension)
class QismExtensionAdmin(admin.ModelAdmin):
    list_display = ('qism', 'weekly_period', 'new_deadline', 'granted_by', 'created_at')
    list_filter = ('weekly_period__year',)
    search_fields = ('qism__name',)
    raw_id_fields = ('qism', 'weekly_period', 'granted_by')
