from rest_framework import serializers


class ReportSummarySerializer(serializers.Serializer):
    period = serializers.DictField(allow_null=True)
    compliance_rate = serializers.FloatField()
    total_submissions = serializers.IntegerField()
    approved_submissions = serializers.IntegerField()
    pending_qualitative = serializers.IntegerField()
    status_breakdown = serializers.DictField()
    target_progress = serializers.ListField()


class PeriodicReportSerializer(serializers.Serializer):
    results = serializers.ListField()
    period_type = serializers.CharField()
    year = serializers.IntegerField()
    period_number = serializers.IntegerField(required=False)
    weeks_count = serializers.IntegerField(required=False)


class ComplianceReportSerializer(serializers.Serializer):
    qism_id = serializers.IntegerField()
    qism_name = serializers.CharField()
    total_periods = serializers.IntegerField()
    submitted = serializers.IntegerField()
    late = serializers.IntegerField()
    not_submitted = serializers.IntegerField()
    compliance_rate = serializers.FloatField()


class QualitativeReportItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    qism_name = serializers.CharField()
    indicator_name = serializers.CharField()
    week_number = serializers.IntegerField()
    qualitative_details = serializers.CharField()
    approved_by = serializers.CharField(allow_null=True)
    approved_at = serializers.DateTimeField(allow_null=True)


class ExportParamsSerializer(serializers.Serializer):
    format = serializers.ChoiceField(choices=['pdf', 'excel'])
    period_type = serializers.ChoiceField(
        choices=['weekly', 'monthly', 'quarterly', 'semi_annual', 'annual']
    )
    year = serializers.IntegerField()
    period_number = serializers.IntegerField(required=False, default=1)
    unit_id = serializers.IntegerField(required=False, allow_null=True)
