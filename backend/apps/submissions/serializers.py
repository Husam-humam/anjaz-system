"""
المسلسلات (Serializers) لتطبيق المنجزات — تحويل البيانات والتحقق من صحتها.
"""
from rest_framework import serializers

from apps.organization.models import OrganizationUnit

from .models import (
    QismExtension,
    SubmissionAnswer,
    WeeklyPeriod,
    WeeklySubmission,
)


# ──────────────────────────────────────────────
# الفترات الأسبوعية
# ──────────────────────────────────────────────

class WeeklyPeriodSerializer(serializers.ModelSerializer):
    """مسلسل الفترة الأسبوعية"""

    class Meta:
        model = WeeklyPeriod
        fields = [
            'id', 'year', 'week_number', 'start_date', 'end_date',
            'deadline', 'status', 'created_by', 'created_at',
        ]
        read_only_fields = ['status', 'created_by', 'created_at']
        extra_kwargs = {
            'year': {
                'error_messages': {
                    'required': 'السنة مطلوبة.',
                    'invalid': 'قيمة السنة غير صالحة.',
                }
            },
            'week_number': {
                'error_messages': {
                    'required': 'رقم الأسبوع مطلوب.',
                    'invalid': 'رقم الأسبوع غير صالح.',
                }
            },
            'start_date': {
                'error_messages': {
                    'required': 'تاريخ البداية مطلوب.',
                    'invalid': 'تاريخ البداية غير صالح.',
                }
            },
            'end_date': {
                'error_messages': {
                    'required': 'تاريخ النهاية مطلوب.',
                    'invalid': 'تاريخ النهاية غير صالح.',
                }
            },
            'deadline': {
                'error_messages': {
                    'required': 'الموعد النهائي مطلوب.',
                    'invalid': 'الموعد النهائي غير صالح.',
                }
            },
        }

    def validate(self, attrs):
        """التحقق من صحة بيانات الفترة الأسبوعية"""
        instance = self.instance or WeeklyPeriod()
        for key, value in attrs.items():
            setattr(instance, key, value)
        instance.clean()
        return attrs


# ──────────────────────────────────────────────
# تمديدات المواعيد
# ──────────────────────────────────────────────

class QismExtensionSerializer(serializers.ModelSerializer):
    """مسلسل تمديد الموعد للقسم"""
    qism_name = serializers.CharField(source='qism.name', read_only=True)

    class Meta:
        model = QismExtension
        fields = [
            'id', 'qism', 'qism_name', 'weekly_period',
            'new_deadline', 'reason', 'granted_by', 'created_at',
        ]
        read_only_fields = ['granted_by', 'created_at']
        extra_kwargs = {
            'qism': {
                'error_messages': {
                    'required': 'القسم مطلوب.',
                    'does_not_exist': 'القسم المحدد غير موجود.',
                }
            },
            'new_deadline': {
                'error_messages': {
                    'required': 'الموعد الجديد مطلوب.',
                    'invalid': 'الموعد الجديد غير صالح.',
                }
            },
            'reason': {
                'error_messages': {
                    'required': 'سبب التمديد مطلوب.',
                    'blank': 'سبب التمديد لا يمكن أن يكون فارغاً.',
                }
            },
        }

    def validate_qism(self, value):
        """التحقق من أن الكيان هو قسم عادي"""
        if value.unit_type != 'qism':
            raise serializers.ValidationError('يجب اختيار قسم فقط.')
        return value

    def validate(self, attrs):
        """التحقق من صحة بيانات التمديد"""
        instance = self.instance or QismExtension()
        for key, value in attrs.items():
            setattr(instance, key, value)
        instance.clean()
        return attrs


# ──────────────────────────────────────────────
# إجابات المنجز
# ──────────────────────────────────────────────

class SubmissionAnswerSerializer(serializers.ModelSerializer):
    """مسلسل إجابة المنجز"""
    indicator_name = serializers.CharField(
        source='form_item.indicator.name', read_only=True
    )
    indicator_unit_type = serializers.CharField(
        source='form_item.indicator.unit_type', read_only=True
    )

    class Meta:
        model = SubmissionAnswer
        fields = [
            'id', 'form_item', 'indicator_name', 'indicator_unit_type',
            'numeric_value', 'text_value', 'is_qualitative',
            'qualitative_details', 'qualitative_status',
        ]
        read_only_fields = ['qualitative_status']
        extra_kwargs = {
            'form_item': {
                'error_messages': {
                    'required': 'بند الاستمارة مطلوب.',
                    'does_not_exist': 'بند الاستمارة المحدد غير موجود.',
                }
            },
        }


# ──────────────────────────────────────────────
# المنجزات الأسبوعية
# ──────────────────────────────────────────────

class WeeklySubmissionSerializer(serializers.ModelSerializer):
    """مسلسل المنجز الأسبوعي — للقراءة"""
    qism_name = serializers.CharField(source='qism.name', read_only=True)
    period_display = serializers.CharField(
        source='weekly_period.__str__', read_only=True
    )
    answers = SubmissionAnswerSerializer(many=True, read_only=True)
    is_editable = serializers.SerializerMethodField()

    class Meta:
        model = WeeklySubmission
        fields = [
            'id', 'qism', 'qism_name', 'weekly_period', 'period_display',
            'form_template', 'status', 'submitted_at',
            'planning_approved_by', 'planning_approved_at',
            'notes', 'answers', 'is_editable',
        ]
        read_only_fields = [
            'qism', 'form_template', 'status', 'submitted_at',
            'planning_approved_by', 'planning_approved_at',
        ]

    def get_is_editable(self, obj):
        """التحقق من إمكانية تعديل المنجز"""
        return obj.is_editable()


class WeeklySubmissionUpdateSerializer(serializers.Serializer):
    """مسلسل تحديث المنجز الأسبوعي — حفظ الإجابات"""
    answers = SubmissionAnswerSerializer(many=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_answers(self, value):
        """التحقق من صحة قائمة الإجابات"""
        if not value:
            raise serializers.ValidationError('يجب إرسال إجابة واحدة على الأقل.')
        # التحقق من عدم تكرار بنود الاستمارة
        form_item_ids = [answer['form_item'].id for answer in value]
        if len(form_item_ids) != len(set(form_item_ids)):
            raise serializers.ValidationError(
                'لا يمكن تكرار نفس بند الاستمارة في الإجابات.'
            )
        return value


# ──────────────────────────────────────────────
# الالتزام
# ──────────────────────────────────────────────

class ComplianceSectionSerializer(serializers.Serializer):
    """مسلسل حالة التزام القسم"""
    qism_id = serializers.IntegerField()
    qism_name = serializers.CharField()
    status = serializers.CharField()


class ComplianceSerializer(serializers.Serializer):
    """مسلسل تقرير الالتزام — استجابة endpoint الالتزام"""
    total_sections = serializers.IntegerField()
    submitted = serializers.IntegerField()
    late = serializers.IntegerField()
    draft = serializers.IntegerField()
    sections = ComplianceSectionSerializer(many=True)


# ──────────────────────────────────────────────
# المنجزات النوعية
# ──────────────────────────────────────────────

class QualitativeAnswerSerializer(serializers.ModelSerializer):
    """مسلسل المنجز النوعي — مع تفاصيل المنجز والقسم"""
    indicator_name = serializers.CharField(
        source='form_item.indicator.name', read_only=True
    )
    indicator_unit_type = serializers.CharField(
        source='form_item.indicator.unit_type', read_only=True
    )
    qism_id = serializers.IntegerField(
        source='submission.qism_id', read_only=True
    )
    qism_name = serializers.CharField(
        source='submission.qism.name', read_only=True
    )
    submission_id = serializers.IntegerField(
        source='submission.id', read_only=True
    )
    weekly_period_id = serializers.IntegerField(
        source='submission.weekly_period_id', read_only=True
    )
    period_display = serializers.CharField(
        source='submission.weekly_period.__str__', read_only=True
    )

    class Meta:
        model = SubmissionAnswer
        fields = [
            'id', 'submission_id', 'qism_id', 'qism_name',
            'weekly_period_id', 'period_display',
            'form_item', 'indicator_name', 'indicator_unit_type',
            'numeric_value', 'text_value', 'is_qualitative',
            'qualitative_details', 'qualitative_status',
            'qualitative_approved_by', 'qualitative_approved_at',
            'rejection_reason',
        ]
        read_only_fields = fields


class QualitativeRejectSerializer(serializers.Serializer):
    """مسلسل رفض المنجز النوعي"""
    rejection_reason = serializers.CharField(
        required=True,
        error_messages={
            'required': 'سبب الرفض مطلوب.',
            'blank': 'سبب الرفض لا يمكن أن يكون فارغاً.',
        }
    )
