from django.contrib import admin
from .models import IndicatorCategory, Indicator


@admin.register(IndicatorCategory)
class IndicatorCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Indicator)
class IndicatorAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'unit_type', 'accumulation_type', 'is_active', 'created_by')
    list_filter = ('unit_type', 'accumulation_type', 'category', 'is_active')
    search_fields = ('name', 'description')
    raw_id_fields = ('created_by',)
