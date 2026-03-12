import io
from collections import defaultdict

from django.db.models import Avg, Count, Q, Sum
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from apps.organization.models import OrganizationUnit
from apps.submissions.models import (SubmissionAnswer, WeeklyPeriod,
                                     WeeklySubmission)
from apps.targets.models import Target


class ReportService:
    """خدمة التقارير"""

    PERIOD_TYPES = {
        'weekly': 1,
        'monthly': 4,  # ~4 أسابيع
        'quarterly': 13,
        'semi_annual': 26,
        'annual': 52,
    }

    @staticmethod
    def get_summary(user, year, week_number=None, unit_id=None):
        """ملخص لوحة التحكم"""
        period_filter = Q(weekly_period__year=year)
        if week_number:
            period_filter &= Q(weekly_period__week_number=week_number)

        # تحديد النطاق بناءً على الصلاحيات
        submissions = WeeklySubmission.objects.filter(period_filter)
        if unit_id:
            unit = OrganizationUnit.objects.get(pk=unit_id)
            descendant_ids = list(unit.get_descendants().values_list('id', flat=True))
            descendant_ids.append(unit.id)
            submissions = submissions.filter(qism_id__in=descendant_ids)
        elif user.role == 'planning_section' and user.unit and user.unit.parent:
            parent = user.unit.parent
            descendant_ids = list(parent.get_descendants().values_list('id', flat=True))
            submissions = submissions.filter(qism_id__in=descendant_ids)
        elif user.role == 'section_manager':
            submissions = submissions.filter(qism=user.unit)

        total = submissions.count()
        status_counts = submissions.values('status').annotate(count=Count('id'))
        status_map = {s['status']: s['count'] for s in status_counts}

        approved_count = status_map.get('approved', 0)
        compliance_rate = (approved_count / total * 100) if total > 0 else 0

        # المنجزات النوعية المعلقة
        pending_qualitative = SubmissionAnswer.objects.filter(
            submission__in=submissions,
            is_qualitative=True,
            qualitative_status__in=['pending_planning', 'pending_statistics'],
        ).count()

        # تقدم المستهدفات
        target_progress = ReportService._get_target_progress(user, year)

        current_period = WeeklyPeriod.objects.filter(year=year).order_by('-week_number').first()
        period_info = None
        if current_period:
            period_info = {
                'year': current_period.year,
                'week_number': current_period.week_number,
                'status': current_period.status,
                'deadline': current_period.deadline.isoformat() if current_period.deadline else None,
            }

        return {
            'period': period_info,
            'compliance_rate': round(compliance_rate, 1),
            'total_submissions': total,
            'approved_submissions': approved_count,
            'pending_qualitative': pending_qualitative,
            'status_breakdown': status_map,
            'target_progress': target_progress,
        }

    @staticmethod
    def get_periodic_report(period_type, year, period_number, unit_id=None):
        """تقرير دوري مجمّع"""
        weeks = ReportService._get_weeks_for_period(period_type, year, period_number)
        if not weeks:
            return {'results': [], 'period_type': period_type, 'year': year}

        week_ids = list(weeks.values_list('id', flat=True))
        submissions = WeeklySubmission.objects.filter(
            weekly_period_id__in=week_ids,
            status='approved',
        ).select_related('qism', 'form_template')

        if unit_id:
            unit = OrganizationUnit.objects.get(pk=unit_id)
            descendant_ids = list(unit.get_descendants().values_list('id', flat=True))
            descendant_ids.append(unit.id)
            submissions = submissions.filter(qism_id__in=descendant_ids)

        answers = SubmissionAnswer.objects.filter(
            submission__in=submissions,
        ).select_related(
            'form_item__indicator', 'submission__qism', 'submission__weekly_period'
        )

        # تجميع حسب القسم والمؤشر
        results = defaultdict(lambda: defaultdict(list))
        for answer in answers:
            if answer.numeric_value is not None:
                key = (answer.submission.qism.name, answer.form_item.indicator.name)
                results[key[0]][key[1]].append({
                    'value': answer.numeric_value,
                    'week': answer.submission.weekly_period.week_number,
                    'accumulation_type': answer.form_item.indicator.accumulation_type,
                })

        # تطبيق التجميع
        report_data = []
        for qism_name, indicators in results.items():
            for indicator_name, values in indicators.items():
                acc_type = values[0]['accumulation_type'] if values else 'sum'
                numeric_values = [v['value'] for v in values]
                aggregated = ReportService._aggregate_values(numeric_values, acc_type)
                report_data.append({
                    'qism_name': qism_name,
                    'indicator_name': indicator_name,
                    'aggregated_value': aggregated,
                    'accumulation_type': acc_type,
                    'data_points': len(numeric_values),
                })

        return {
            'results': report_data,
            'period_type': period_type,
            'year': year,
            'period_number': period_number,
            'weeks_count': len(week_ids),
        }

    @staticmethod
    def get_compliance_report(year, unit_id=None):
        """تقرير الامتثال"""
        periods = WeeklyPeriod.objects.filter(year=year).order_by('week_number')
        qisms = OrganizationUnit.objects.filter(
            unit_type='qism', qism_role='regular', is_active=True
        )
        if unit_id:
            unit = OrganizationUnit.objects.get(pk=unit_id)
            descendant_ids = list(unit.get_descendants().values_list('id', flat=True))
            qisms = qisms.filter(id__in=descendant_ids)

        compliance_data = []
        for qism in qisms:
            qism_submissions = WeeklySubmission.objects.filter(
                qism=qism, weekly_period__in=periods
            )
            total_periods = periods.count()
            submitted = qism_submissions.filter(
                status__in=['submitted', 'approved']
            ).count()
            late = qism_submissions.filter(status='late').count()

            compliance_data.append({
                'qism_id': qism.id,
                'qism_name': qism.name,
                'total_periods': total_periods,
                'submitted': submitted,
                'late': late,
                'not_submitted': total_periods - submitted - late,
                'compliance_rate': round(submitted / total_periods * 100, 1) if total_periods > 0 else 0,
            })

        return compliance_data

    @staticmethod
    def get_qualitative_report(year, unit_id=None, from_week=None, to_week=None):
        """تقرير المنجزات النوعية"""
        filters = Q(
            is_qualitative=True,
            qualitative_status='approved',
            submission__weekly_period__year=year,
        )
        if from_week:
            filters &= Q(submission__weekly_period__week_number__gte=from_week)
        if to_week:
            filters &= Q(submission__weekly_period__week_number__lte=to_week)
        if unit_id:
            unit = OrganizationUnit.objects.get(pk=unit_id)
            descendant_ids = list(unit.get_descendants().values_list('id', flat=True))
            descendant_ids.append(unit.id)
            filters &= Q(submission__qism_id__in=descendant_ids)

        return SubmissionAnswer.objects.filter(filters).select_related(
            'form_item__indicator', 'submission__qism', 'submission__weekly_period',
            'qualitative_approved_by'
        ).order_by('-submission__weekly_period__week_number')

    @staticmethod
    def export_excel(report_data, report_title):
        """تصدير التقرير بصيغة Excel"""
        wb = Workbook()
        ws = wb.active
        ws.title = report_title[:31]
        ws.sheet_properties.isRightToLeft = True

        # العنوان
        ws.append([report_title])
        ws.append([])

        # الرؤوس
        if report_data.get('results'):
            headers = ['القسم', 'المؤشر', 'القيمة المجمعة', 'طريقة التجميع', 'عدد نقاط البيانات']
            ws.append(headers)
            for row in report_data['results']:
                ws.append([
                    row.get('qism_name', ''),
                    row.get('indicator_name', ''),
                    row.get('aggregated_value') if row.get('aggregated_value') is not None else '-',
                    row.get('accumulation_type', ''),
                    row.get('data_points', ''),
                ])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @staticmethod
    def export_pdf(report_data, report_title):
        """تصدير التقرير بصيغة PDF"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            rightMargin=1.5 * cm, leftMargin=1.5 * cm,
            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        )

        elements = []
        styles = getSampleStyleSheet()

        # العنوان
        title_style = ParagraphStyle(
            'ArabicTitle', parent=styles['Heading1'],
            alignment=1,  # center
        )
        elements.append(Paragraph(report_title, title_style))
        elements.append(Spacer(1, 0.5 * cm))

        # الجدول
        if report_data.get('results'):
            table_data = [
                ['القسم', 'المؤشر', 'القيمة', 'التجميع', 'نقاط البيانات']
            ]
            for row in report_data['results']:
                table_data.append([
                    str(row.get('qism_name', '')),
                    str(row.get('indicator_name', '')),
                    str(row.get('aggregated_value')) if row.get('aggregated_value') is not None else '-',
                    str(row.get('accumulation_type', '')),
                    str(row.get('data_points', '')),
                ])

            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1d4ed8')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
            ]))
            elements.append(table)

        doc.build(elements)
        buffer.seek(0)
        return buffer

    # --- Helper methods ---

    @staticmethod
    def _get_weeks_for_period(period_type, year, period_number):
        """الحصول على الأسابيع لفترة معينة"""
        if period_type == 'weekly':
            return WeeklyPeriod.objects.filter(year=year, week_number=period_number)
        elif period_type == 'monthly':
            start_week = (period_number - 1) * 4 + 1
            end_week = start_week + 4
            return WeeklyPeriod.objects.filter(
                year=year, week_number__gte=start_week, week_number__lt=end_week
            )
        elif period_type == 'quarterly':
            start_week = (period_number - 1) * 13 + 1
            end_week = start_week + 13
            return WeeklyPeriod.objects.filter(
                year=year, week_number__gte=start_week, week_number__lt=end_week
            )
        elif period_type == 'semi_annual':
            start_week = (period_number - 1) * 26 + 1
            end_week = start_week + 26
            return WeeklyPeriod.objects.filter(
                year=year, week_number__gte=start_week, week_number__lt=end_week
            )
        elif period_type == 'annual':
            return WeeklyPeriod.objects.filter(year=year)
        return WeeklyPeriod.objects.none()

    @staticmethod
    def _aggregate_values(values, accumulation_type):
        """تجميع القيم حسب النوع"""
        if not values:
            return 0
        if accumulation_type == 'sum':
            return sum(values)
        elif accumulation_type == 'average':
            return round(sum(values) / len(values), 2)
        elif accumulation_type == 'last_value':
            return values[-1]
        return sum(values)

    @staticmethod
    def _get_target_progress(user, year):
        """حساب تقدم المستهدفات"""
        targets = Target.objects.filter(year=year).select_related('qism', 'indicator')

        if user.role == 'section_manager':
            targets = targets.filter(qism=user.unit)
        elif user.role == 'planning_section' and user.unit and user.unit.parent:
            parent = user.unit.parent
            descendant_ids = list(parent.get_descendants().values_list('id', flat=True))
            targets = targets.filter(qism_id__in=descendant_ids)

        progress_list = []
        for target in targets[:10]:  # أعلى 10
            cumulative = SubmissionAnswer.objects.filter(
                submission__qism=target.qism,
                submission__weekly_period__year=year,
                submission__status='approved',
                form_item__indicator=target.indicator,
                numeric_value__isnull=False,
            )
            if target.indicator.accumulation_type == 'sum':
                result = cumulative.aggregate(total=Sum('numeric_value'))
                cumulative_value = result['total'] or 0
            elif target.indicator.accumulation_type == 'average':
                result = cumulative.aggregate(avg=Avg('numeric_value'))
                cumulative_value = result['avg'] or 0
            else:
                last = cumulative.order_by(
                    '-submission__weekly_period__week_number'
                ).first()
                cumulative_value = last.numeric_value if last else 0

            progress_pct = (cumulative_value / target.target_value * 100) if target.target_value > 0 else 0

            progress_list.append({
                'indicator_name': target.indicator.name,
                'qism_name': target.qism.name,
                'cumulative_value': round(cumulative_value, 2),
                'target_value': target.target_value,
                'progress_percentage': round(progress_pct, 1),
            })

        return progress_list
