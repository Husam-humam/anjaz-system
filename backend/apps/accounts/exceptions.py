"""
معالج الاستثناءات المخصص لنظام إنجاز.
يوحّد شكل الاستجابة لجميع أخطاء الـ API.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


# خريطة رموز حالة HTTP إلى رموز الخطأ الداخلية
STATUS_CODE_MAP = {
    status.HTTP_400_BAD_REQUEST: 'VALIDATION_ERROR',
    status.HTTP_401_UNAUTHORIZED: 'AUTHENTICATION_ERROR',
    status.HTTP_403_FORBIDDEN: 'PERMISSION_DENIED',
    status.HTTP_404_NOT_FOUND: 'NOT_FOUND',
    status.HTTP_409_CONFLICT: 'CONFLICT',
    status.HTTP_422_UNPROCESSABLE_ENTITY: 'BUSINESS_RULE_VIOLATION',
}

# رسائل افتراضية لبعض رموز الحالة
DEFAULT_MESSAGES = {
    status.HTTP_400_BAD_REQUEST: 'بيانات غير صالحة. يرجى التحقق من المدخلات.',
    status.HTTP_401_UNAUTHORIZED: 'يرجى تسجيل الدخول للمتابعة.',
    status.HTTP_403_FORBIDDEN: 'ليس لديك صلاحية للقيام بهذا الإجراء',
    status.HTTP_404_NOT_FOUND: 'العنصر المطلوب غير موجود',
    status.HTTP_409_CONFLICT: 'يوجد تعارض مع البيانات الحالية.',
    status.HTTP_422_UNPROCESSABLE_ENTITY: 'لا يمكن تنفيذ العملية بسبب مخالفة لقواعد العمل.',
}


def custom_exception_handler(exc, context):
    """
    معالج استثناءات مخصص لـ DRF يُرجع جميع الأخطاء بتنسيق موحّد:
    {
        "error": true,
        "message": "رسالة خطأ واضحة للمستخدم",
        "code": "VALIDATION_ERROR",
        "details": { "field_name": ["رسالة خطأ الحقل"] }
    }
    """
    # استدعاء المعالج الافتراضي أولاً
    response = exception_handler(exc, context)

    if response is None:
        return None

    status_code = response.status_code
    error_code = STATUS_CODE_MAP.get(status_code, 'SERVER_ERROR')
    default_message = DEFAULT_MESSAGES.get(status_code, 'حدث خطأ غير متوقع.')

    # استخراج التفاصيل والرسالة من بيانات الاستجابة
    response_data = response.data
    details = {}
    message = default_message

    if isinstance(response_data, dict):
        # إذا كان هناك حقل 'detail' فهو رسالة عامة من DRF
        if 'detail' in response_data:
            detail_value = response_data['detail']
            if isinstance(detail_value, list):
                message = ' '.join(str(item) for item in detail_value)
            else:
                message = str(detail_value)
            # إزالة 'detail' من التفاصيل لأنها أصبحت الرسالة الرئيسية
            remaining = {k: v for k, v in response_data.items() if k != 'detail'}
            if remaining:
                details = remaining
        else:
            # أخطاء حقول (validation errors)
            details = response_data
    elif isinstance(response_data, list):
        # قائمة أخطاء عامة
        message = ' '.join(str(item) for item in response_data)

    # بناء الاستجابة الموحّدة
    error_response = {
        'error': True,
        'message': message,
        'code': error_code,
        'details': details,
    }

    response.data = error_response
    return response
