from django.contrib import admin
from mptt.admin import MPTTModelAdmin

from .models import (
    OrganizationUnit,
    PlanningAssignment,
    SupervisedUnit,
    ViewScope,
)


@admin.register(OrganizationUnit)
class OrganizationUnitAdmin(MPTTModelAdmin):
    list_display = ('name', 'code', 'unit_type', 'parent', 'is_active', 'external_id')
    list_filter = ('unit_type', 'is_active')
    search_fields = ('name', 'code', 'external_id')
    readonly_fields = ('external_id', 'external_synced_at')


class SupervisedUnitInline(admin.TabularInline):
    model = SupervisedUnit
    extra = 0
    autocomplete_fields = ('unit',)


@admin.register(PlanningAssignment)
class PlanningAssignmentAdmin(admin.ModelAdmin):
    list_display = ('planning_unit', 'context_parent', 'created_at', 'created_by')
    search_fields = ('planning_unit__name', 'planning_unit__code')
    autocomplete_fields = ('planning_unit', 'context_parent', 'created_by')
    inlines = [SupervisedUnitInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SupervisedUnit)
class SupervisedUnitAdmin(admin.ModelAdmin):
    list_display = ('unit', 'assignment', 'created_at')
    search_fields = ('unit__name', 'assignment__planning_unit__name')
    autocomplete_fields = ('unit', 'assignment')


@admin.register(ViewScope)
class ViewScopeAdmin(admin.ModelAdmin):
    list_display = ('user', 'units_count', 'created_at', 'created_by')
    search_fields = ('user__username', 'user__full_name')
    autocomplete_fields = ('user', 'created_by')
    filter_horizontal = ('viewable_units',)
    readonly_fields = ('created_at', 'updated_at')

    def units_count(self, obj):
        return obj.viewable_units.count()
    units_count.short_description = 'عدد الوحدات'
