from django.contrib import admin

from .models import Target


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'scope_display', 'indicator_count', 'year', 'target_value', 'set_by',
    )
    list_filter = ('year',)
    search_fields = (
        'name', 'scope_unit__name', 'scope_unit__code',
        'indicators__name', 'notes',
    )
    raw_id_fields = ('scope_unit', 'set_by')
    filter_horizontal = ('indicators',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('بيانات المستهدف', {
            'fields': ('name', 'scope_unit', 'indicators', 'year', 'target_value', 'notes'),
            'description': (
                'اترك "نطاق المستهدف" فارغاً لإنشاء مستهدف على مستوى المؤسسة كاملة. '
                'كل المؤشّرات المختارة يجب أن تكون بنفس نوع الوحدة.'
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

    @admin.display(description='عدد المكوّنات')
    def indicator_count(self, obj):
        return obj.indicators.count()
