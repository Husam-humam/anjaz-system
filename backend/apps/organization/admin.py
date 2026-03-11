from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from .models import OrganizationUnit


@admin.register(OrganizationUnit)
class OrganizationUnitAdmin(MPTTModelAdmin):
    list_display = ('name', 'code', 'unit_type', 'qism_role', 'parent', 'is_active')
    list_filter = ('unit_type', 'qism_role', 'is_active')
    search_fields = ('name', 'code')
