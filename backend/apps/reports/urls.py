from django.urls import path

from .views import (ComplianceReportView, PeriodicReportView,
                    QualitativeReportView, ReportExportView,
                    ReportSummaryView)

urlpatterns = [
    path('summary/', ReportSummaryView.as_view(), name='report-summary'),
    path('periodic/', PeriodicReportView.as_view(), name='report-periodic'),
    path('compliance/', ComplianceReportView.as_view(), name='report-compliance'),
    path('qualitative/', QualitativeReportView.as_view(), name='report-qualitative'),
    path('export/', ReportExportView.as_view(), name='report-export'),
]
