from django.contrib import admin
from .models import FormTemplate, FormTemplateItem


class FormTemplateItemInline(admin.TabularInline):
    model = FormTemplateItem
    extra = 1
    raw_id_fields = ('indicator',)


@admin.register(FormTemplate)
class FormTemplateAdmin(admin.ModelAdmin):
    list_display = ('qism', 'version', 'status', 'effective_from_week', 'effective_from_year', 'created_by', 'approved_by')
    list_filter = ('status', 'effective_from_year')
    search_fields = ('qism__name',)
    raw_id_fields = ('qism', 'created_by', 'approved_by', 'rejected_by')
    inlines = [FormTemplateItemInline]


@admin.register(FormTemplateItem)
class FormTemplateItemAdmin(admin.ModelAdmin):
    list_display = ('form_template', 'indicator', 'is_mandatory', 'display_order')
    list_filter = ('is_mandatory',)
    search_fields = ('indicator__name', 'form_template__qism__name')
    raw_id_fields = ('form_template', 'indicator')
