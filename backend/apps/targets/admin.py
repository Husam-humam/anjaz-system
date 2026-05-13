from django.contrib import admin

from .models import Target


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = (
        'scope_display', 'indicator', 'year', 'target_value', 'set_by',
    )
    list_filter = ('year', 'indicator__category')
    search_fields = (
        'scope_unit__name', 'scope_unit__code', 'indicator__name', 'notes',
    )
    raw_id_fields = ('scope_unit', 'indicator', 'set_by')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('بيانات المستهدف', {
            'fields': ('scope_unit', 'indicator', 'year', 'target_value', 'notes'),
            'description': (
                'اترك "نطاق المستهدف" فارغاً لإنشاء مستهدف على مستوى المؤسسة كاملة. '
                'أو اختر دائرة/مديرية/قسم لتحديد النطاق.'
            ),
        }),
        ('معلومات النظام', {
            'fields': ('set_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='النطاق')
    def scope_display(self, obj):
        if obj.scope_unit_id is None:
            return 'المؤسسة كاملة'
        return f'{obj.scope_unit.get_unit_type_display()}: {obj.scope_unit.name}'
