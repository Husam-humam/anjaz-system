from django.contrib import admin
from .models import WeeklyPeriod, WeeklySubmission, SubmissionAnswer, QismExtension


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
