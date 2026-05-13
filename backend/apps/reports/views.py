from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (ComplianceReportSerializer, ExportParamsSerializer,
                          PeriodicReportSerializer, QualitativeReportItemSerializer,
                          ReportSummarySerializer)
from .services import ReportService


def _validate_unit_scope(request, unit_id):
    """التحقق من نطاق صلاحية المستخدم على الوحدة المحددة"""
    if unit_id is None:
        return None
    if request.user.role == 'statistics_admin':
        return None
    if request.user.role == 'section_manager':
        if request.user.unit_id != unit_id:
            return Response(
                {'detail': 'لا تملك صلاحية الوصول لهذه الوحدة'},
                status=status.HTTP_403_FORBIDDEN,
            )
    elif request.user.role == 'planning_section' and request.user.unit:
        parent = request.user.unit.parent
        if parent:
            allowed_ids = list(parent.get_descendants().values_list('id', flat=True))
            allowed_ids.append(parent.id)
            if unit_id not in allowed_ids:
                return Response(
                    {'detail': 'لا تملك صلاحية الوصول لهذه الوحدة'},
                    status=status.HTTP_403_FORBIDDEN,
                )
    return None


class ReportSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # التحقق من الصلاحيات
        try:
            year = int(request.query_params.get('year', timezone.now().year))
        except (ValueError, TypeError):
            return Response({'detail': 'قيمة السنة غير صالحة'}, status=status.HTTP_400_BAD_REQUEST)

        week_number = request.query_params.get('week_number')
        if week_number:
            try:
                week_number = int(week_number)
            except (ValueError, TypeError):
                return Response({'detail': 'رقم الأسبوع غير صالح'}, status=status.HTTP_400_BAD_REQUEST)

        unit_id = request.query_params.get('unit_id')
        if unit_id:
            try:
                unit_id = int(unit_id)
            except (ValueError, TypeError):
                return Response({'detail': 'معرف الوحدة غير صالح'}, status=status.HTTP_400_BAD_REQUEST)
            # التحقق من نطاق الصلاحية
            scope_error = _validate_unit_scope(request, unit_id)
            if scope_error:
                return scope_error

        data = ReportService.get_summary(request.user, year, week_number, unit_id)
        return Response(data)


class PeriodicReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        import datetime

        # نمطان مدعومان:
        # 1) date range: from_date + to_date (ISO: YYYY-MM-DD)
        # 2) period_type + year + period_number
        from_date_str = request.query_params.get('from_date')
        to_date_str = request.query_params.get('to_date')

        from_date = None
        to_date = None
        if from_date_str and to_date_str:
            try:
                from_date = datetime.date.fromisoformat(from_date_str)
                to_date = datetime.date.fromisoformat(to_date_str)
            except ValueError:
                return Response(
                    {'detail': 'تنسيق التاريخ غير صالح. استخدم YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if from_date > to_date:
                return Response(
                    {'detail': 'تاريخ البداية يجب أن يكون قبل تاريخ النهاية'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        period_type = request.query_params.get('period_type', 'weekly')
        try:
            year = int(request.query_params.get('year', timezone.now().year))
        except (ValueError, TypeError):
            return Response(
                {'detail': 'قيمة السنة غير صالحة'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            period_number = int(request.query_params.get('period_number', 1))
        except (ValueError, TypeError):
            return Response(
                {'detail': 'رقم الفترة غير صالح'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        unit_id = request.query_params.get('unit_id')
        if unit_id:
            try:
                unit_id = int(unit_id)
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'معرف الوحدة غير صالح'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            scope_error = _validate_unit_scope(request, unit_id)
            if scope_error:
                return scope_error

        data = ReportService.get_periodic_report(
            period_type=period_type if not from_date else None,
            year=year if not from_date else None,
            period_number=period_number if not from_date else None,
            unit_id=unit_id,
            from_date=from_date,
            to_date=to_date,
        )
        return Response(data)


class ComplianceReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # التحقق من الصلاحيات
        try:
            year = int(request.query_params.get('year', timezone.now().year))
        except (ValueError, TypeError):
            return Response({'detail': 'قيمة السنة غير صالحة'}, status=status.HTTP_400_BAD_REQUEST)

        unit_id = request.query_params.get('unit_id')
        if unit_id:
            try:
                unit_id = int(unit_id)
            except (ValueError, TypeError):
                return Response({'detail': 'معرف الوحدة غير صالح'}, status=status.HTTP_400_BAD_REQUEST)
            # التحقق من نطاق الصلاحية
            scope_error = _validate_unit_scope(request, unit_id)
            if scope_error:
                return scope_error

        data = ReportService.get_compliance_report(year, unit_id)
        serializer = ComplianceReportSerializer(data, many=True)
        return Response(serializer.data)


class QualitativeReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # التحقق من الصلاحيات
        try:
            year = int(request.query_params.get('year', timezone.now().year))
        except (ValueError, TypeError):
            return Response({'detail': 'قيمة السنة غير صالحة'}, status=status.HTTP_400_BAD_REQUEST)

        unit_id = request.query_params.get('unit_id')
        if unit_id:
            try:
                unit_id = int(unit_id)
            except (ValueError, TypeError):
                return Response({'detail': 'معرف الوحدة غير صالح'}, status=status.HTTP_400_BAD_REQUEST)
            # التحقق من نطاق الصلاحية
            scope_error = _validate_unit_scope(request, unit_id)
            if scope_error:
                return scope_error

        from_week = request.query_params.get('from_week')
        to_week = request.query_params.get('to_week')
        if from_week:
            try:
                from_week = int(from_week)
            except (ValueError, TypeError):
                return Response({'detail': 'رقم أسبوع البداية غير صالح'}, status=status.HTTP_400_BAD_REQUEST)
        if to_week:
            try:
                to_week = int(to_week)
            except (ValueError, TypeError):
                return Response({'detail': 'رقم أسبوع النهاية غير صالح'}, status=status.HTTP_400_BAD_REQUEST)

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

        # التحقق من نطاق الصلاحية
        if unit_id:
            scope_error = _validate_unit_scope(request, unit_id)
            if scope_error:
                return scope_error

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
