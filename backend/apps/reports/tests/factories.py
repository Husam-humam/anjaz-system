"""
مصانع البيانات التجريبية لتطبيق التقارير.
تطبيق التقارير لا يملك نماذج خاصة - يُعاد تصدير المصانع المستخدمة من التطبيقات الأخرى.
"""
from apps.accounts.tests.factories import (  # noqa: F401
    PlanningSectionUserFactory,
    SectionManagerFactory,
    StatisticsAdminFactory,
)
from apps.forms.tests.factories import (  # noqa: F401
    FormTemplateFactory,
    FormTemplateItemFactory,
)
from apps.indicators.tests.factories import IndicatorFactory  # noqa: F401
from apps.organization.tests.factories import (  # noqa: F401
    DairaFactory,
    MudiriyaFactory,
    QismFactory,
)
from apps.submissions.tests.factories import (  # noqa: F401
    SubmissionAnswerFactory,
    WeeklyPeriodFactory,
    WeeklySubmissionFactory,
)
