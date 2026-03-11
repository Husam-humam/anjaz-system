from django.contrib import admin
from .models import Target


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = ('qism', 'indicator', 'year', 'target_value', 'set_by')
    list_filter = ('year',)
    search_fields = ('qism__name', 'indicator__name')
    raw_id_fields = ('qism', 'indicator', 'set_by')
