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
    def get_periodic_report(
        period_type=None, year=None, period_number=None,
        unit_id=None, from_date=None, to_date=None,
    ):
        """
        تقرير دوري مجمّع — يدعم نمطين:
        1) الكلاسيكي: period_type + year + period_number
        2) الجديد: from_date + to_date (date range)

        يُرجع:
        {
            'results': [...],           # كل (قسم، مؤشر) مع القيمة المُجمّعة
            'indicator_summary': [...], # ملخّص لكل مؤشر على مستوى النطاق كاملاً
            'meta': {'weeks_count', 'from_date', 'to_date', ...}
        }
        """
        # تحديد مجموعة الأسابيع
        if from_date and to_date:
            weeks = WeeklyPeriod.objects.filter(
                start_date__lte=to_date,
                end_date__gte=from_date,
            )
        elif period_type and year:
            weeks = ReportService._get_weeks_for_period(
                period_type, year, period_number
            )
        else:
            return {
                'results': [],
                'indicator_summary': [],
                'meta': {'weeks_count': 0},
            }

        if not weeks.exists():
            return {
                'results': [],
                'indicator_summary': [],
                'meta': {
                    'weeks_count': 0,
                    'period_type': period_type,
                    'year': year,
                    'period_number': period_number,
                    'from_date': str(from_date) if from_date else None,
                    'to_date': str(to_date) if to_date else None,
                },
            }

        week_ids = list(weeks.values_list('id', flat=True))
        submissions = WeeklySubmission.objects.filter(
            weekly_period_id__in=week_ids,
            status__in=['submitted', 'approved'],
        ).select_related('qism', 'form_template')

        # تصفية حسب الوحدة (تُشمل أقسام الأحفاد)
        if unit_id:
            unit = OrganizationUnit.objects.get(pk=unit_id)
            descendant_ids = list(
                unit.get_descendants().values_list('id', flat=True)
            )
            descendant_ids.append(unit.id)
            submissions = submissions.filter(qism_id__in=descendant_ids)

        # الترتيب حسب (سنة، رقم الأسبوع) ضروري لصحة aggregation='last_value'
        # — حتى يكون آخر عنصر في القائمة هو فعلاً الأحدث زمنياً.
        answers = SubmissionAnswer.objects.filter(
            submission__in=submissions,
        ).select_related(
            'form_item__indicator', 'form_item__indicator__category',
            'submission__qism', 'submission__weekly_period',
        ).order_by(
            'submission__weekly_period__year',
            'submission__weekly_period__week_number',
        )

        # تجميع حسب (qism_id, indicator_id)
        by_qism_indicator = defaultdict(
            lambda: {'values': [], 'qism': None, 'indicator': None}
        )
        by_indicator = defaultdict(
            lambda: {'values': [], 'indicator': None, 'qism_ids': set()}
        )

        for answer in answers:
            if answer.numeric_value is None:
                continue
            qism = answer.submission.qism
            indicator = answer.form_item.indicator

            key = (qism.id, indicator.id)
            by_qism_indicator[key]['values'].append(answer.numeric_value)
            by_qism_indicator[key]['qism'] = qism
            by_qism_indicator[key]['indicator'] = indicator

            by_indicator[indicator.id]['values'].append(answer.numeric_value)
            by_indicator[indicator.id]['indicator'] = indicator
            by_indicator[indicator.id]['qism_ids'].add(qism.id)

        # النتائج التفصيلية (قسم × مؤشر)
        report_data = []
        for (qism_id, indicator_id), bucket in by_qism_indicator.items():
            qism = bucket['qism']
            indicator = bucket['indicator']
            acc_type = indicator.accumulation_type
            aggregated = ReportService._aggregate_values(
                bucket['values'], acc_type
            )
            # الوحدة الأم المباشرة + الجد للعرض الهرمي
            parent = qism.parent
            grandparent = parent.parent if parent else None
            report_data.append({
                'qism_id': qism.id,
                'qism_name': qism.name,
                'qism_code': qism.code,
                'parent_id': parent.id if parent else None,
                'parent_name': parent.name if parent else None,
                'grandparent_id': grandparent.id if grandparent else None,
                'grandparent_name': grandparent.name if grandparent else None,
                'indicator_id': indicator.id,
                'indicator_name': indicator.name,
                'indicator_category': (
                    indicator.category.name if indicator.category_id else None
                ),
                'aggregated_value': aggregated,
                'accumulation_type': acc_type,
                'data_points': len(bucket['values']),
            })

        # ملخّص لكل مؤشر على مستوى النطاق كاملاً
        indicator_summary = []
        for ind_id, bucket in by_indicator.items():
            indicator = bucket['indicator']
            acc_type = indicator.accumulation_type
            total = ReportService._aggregate_values(
                bucket['values'], acc_type
            )
            indicator_summary.append({
                'indicator_id': ind_id,
                'indicator_name': indicator.name,
                'indicator_category': (
                    indicator.category.name if indicator.category_id else None
                ),
                'total_value': total,
                'accumulation_type': acc_type,
                'contributing_qisms': len(bucket['qism_ids']),
                'data_points': len(bucket['values']),
            })
        # ترتيب حسب التصنيف ثم الاسم
        indicator_summary.sort(
            key=lambda x: (x['indicator_category'] or '', x['indicator_name'])
        )

        return {
            'results': report_data,
            'indicator_summary': indicator_summary,
            'meta': {
                'weeks_count': len(week_ids),
                'period_type': period_type,
                'year': year,
                'period_number': period_number,
                'from_date': str(from_date) if from_date else None,
                'to_date': str(to_date) if to_date else None,
            },
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
            # include_self=True حتى إذا كان `unit` نفسه قسماً يُدرَج في التقرير.
            descendant_ids = list(
                unit.get_descendants(include_self=True).values_list('id', flat=True)
            )
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
        from django.utils import timezone as dj_timezone

        wb = Workbook()
        ws = wb.active
        ws.title = report_title[:31]
        ws.sheet_properties.isRightToLeft = True

        # العنوان
        ws.append([report_title])
        # ختم زمني للتوليد — التقارير «حيّة» وقد تختلف عند مراجعة لاحقة من الإحصاء.
        generated_at = dj_timezone.localtime().strftime('%Y-%m-%d %H:%M')
        ws.append([f'تاريخ توليد التقرير: {generated_at}'])
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
        from django.utils import timezone as dj_timezone

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

        # ختم زمني للتوليد — يُذكّر القارئ أن التقرير snapshot لحظي،
        # وأي تعديل لاحق من الإحصاء قد يُغيّر الأرقام في النظام.
        generated_at = dj_timezone.localtime().strftime('%Y-%m-%d %H:%M')
        timestamp_style = ParagraphStyle(
            'ArabicTimestamp', parent=styles['Normal'],
            alignment=1, fontSize=8, textColor=colors.grey,
        )
        elements.append(
            Paragraph(f'تاريخ توليد التقرير: {generated_at}', timestamp_style)
        )
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
        """
        حساب تقدم المستهدفات الهرمية (مؤسسة/دائرة/مديرية/قسم).
        يستخدم TargetService.compute_target_progress للحساب الموحّد.
        يُرجع كل المستهدفات المرئية للمستخدم (دون حد `[:10]`).
        """
        from apps.targets.services import TargetService

        targets = Target.objects.filter(year=year).select_related(
            'scope_unit', 'scope_unit__parent',
            'indicator',
        ).order_by('scope_unit__name', 'indicator__name')

        # تصفية حسب الدور (نفس منطق TargetViewSet.get_queryset للاتساق)
        if user.role == 'statistics_admin':
            pass
        elif user.role == 'planning_section':
            if user.unit and user.unit.parent:
                directorate = user.unit.parent
                descendant_ids = list(
                    directorate.get_descendants(include_self=True)
                    .values_list('id', flat=True)
                )
                ancestor_ids = list(
                    directorate.get_ancestors().values_list('id', flat=True)
                )
                visible_ids = set(descendant_ids) | set(ancestor_ids)
                from django.db.models import Q
                targets = targets.filter(
                    Q(scope_unit__isnull=True) |
                    Q(scope_unit_id__in=visible_ids)
                )
            else:
                targets = targets.filter(scope_unit__isnull=True)
        elif user.role == 'section_manager' and user.unit:
            from django.db.models import Q
            ancestors_ids = list(
                user.unit.get_ancestors(include_self=False)
                .values_list('id', flat=True)
            )
            targets = targets.filter(
                Q(scope_unit__isnull=True) |
                Q(scope_unit=user.unit) |
                Q(scope_unit_id__in=ancestors_ids)
            )
        else:
            targets = targets.none()

        progress_list = []
        for target in targets:
            progress = TargetService.compute_target_progress(target)
            scope_name = (
                target.scope_unit.name if target.scope_unit_id
                else 'المؤسسة كاملة'
            )
            progress_list.append({
                'target_id': target.id,
                'indicator_name': target.indicator.name,
                # للتوافق مع الفرونت القديم نُبقي على مفتاح qism_name
                'qism_name': scope_name,
                'scope_unit_name': scope_name,
                'scope_level': target.scope_level,
                'cumulative_value': progress['cumulative_value'],
                'target_value': progress['target_value'],
                'progress_percentage': progress['progress_percentage'],
            })

        return progress_list
