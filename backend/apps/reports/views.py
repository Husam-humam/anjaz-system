from django.http import FileResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (ComplianceReportSerializer, ExportParamsSerializer,
                          PeriodicReportSerializer, QualitativeReportItemSerializer,
                          ReportSummarySerializer)
from .services import ReportService


class ReportSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = int(request.query_params.get('year', 2025))
        week_number = request.query_params.get('week_number')
        unit_id = request.query_params.get('unit_id')

        if week_number:
            week_number = int(week_number)
        if unit_id:
            unit_id = int(unit_id)

        data = ReportService.get_summary(request.user, year, week_number, unit_id)
        return Response(data)


class PeriodicReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period_type = request.query_params.get('period_type', 'weekly')
        year = int(request.query_params.get('year', 2025))
        period_number = int(request.query_params.get('period_number', 1))
        unit_id = request.query_params.get('unit_id')

        if unit_id:
            unit_id = int(unit_id)

        data = ReportService.get_periodic_report(period_type, year, period_number, unit_id)
        return Response(data)


class ComplianceReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = int(request.query_params.get('year', 2025))
        unit_id = request.query_params.get('unit_id')

        if unit_id:
            unit_id = int(unit_id)

        data = ReportService.get_compliance_report(year, unit_id)
        serializer = ComplianceReportSerializer(data, many=True)
        return Response(serializer.data)


class QualitativeReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = int(request.query_params.get('year', 2025))
        unit_id = request.query_params.get('unit_id')
        from_week = request.query_params.get('from_week')
        to_week = request.query_params.get('to_week')

        if unit_id:
            unit_id = int(unit_id)
        if from_week:
            from_week = int(from_week)
        if to_week:
            to_week = int(to_week)

        queryset = ReportService.get_qualitative_report(year, unit_id, from_week, to_week)

        results = []
        for answer in queryset:
            results.append({
                'id': answer.id,
                'qism_name': answer.submission.qism.name,
                'indicator_name': answer.form_item.indicator.name,
                'week_number': answer.submission.weekly_period.week_number,
                'qualitative_details': answer.qualitative_details,
                'approved_by': answer.qualitative_approved_by.full_name if answer.qualitative_approved_by else None,
                'approved_at': answer.qualitative_approved_at,
            })

        return Response(results)


class ReportExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ExportParamsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data

        export_format = params['format']
        period_type = params['period_type']
        year = params['year']
        period_number = params.get('period_number', 1)
        unit_id = params.get('unit_id')

        report_data = ReportService.get_periodic_report(
            period_type, year, period_number, unit_id
        )

        period_names = {
            'weekly': f'الأسبوع {period_number}',
            'monthly': f'الشهر {period_number}',
            'quarterly': f'الربع {period_number}',
            'semi_annual': f'النصف {"الأول" if period_number == 1 else "الثاني"}',
            'annual': 'سنوي',
        }
        report_title = f'تقرير {period_names.get(period_type, "")} - {year}'

        if export_format == 'excel':
            output = ReportService.export_excel(report_data, report_title)
            return FileResponse(
                output,
                as_attachment=True,
                filename=f'report_{period_type}_{year}_{period_number}.xlsx',
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
        else:
            output = ReportService.export_pdf(report_data, report_title)
            return FileResponse(
                output,
                as_attachment=True,
                filename=f'report_{period_type}_{year}_{period_number}.pdf',
                content_type='application/pdf',
            )
