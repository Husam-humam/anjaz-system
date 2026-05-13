"""
خدمة سجلّ التدقيق (Audit Log Service).

التصميم:
- نقطة دخول موحّدة `AuditService.log(...)` تُستخدم من جميع خدمات الأعمال.
- تُطبَّق عبر طبقة الخدمة (service layer) وليس عبر signals، لأن الـ signals
  لا يصلها سياق المستخدم (`actor`) ولا السبب (`reason`) بشكل نظيف.
- تُستدعى داخل نفس `@transaction.atomic` للعملية الأصليّة، فإن تراجعت
  العمليّة تتراجع كتابة الـ audit أيضاً (لا يُسجَّل إجراء لم يحدث فعلاً).
"""
import logging

from .models import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """خدمة موحّدة لكتابة سجلّ التدقيق."""

    @staticmethod
    def log(
        action_type,
        actor=None,
        target=None,
        target_model=None,
        target_id=None,
        target_repr='',
        qism=None,
        field_changes=None,
        reason='',
        metadata=None,
    ):
        """
        كتابة سطر في سجلّ التدقيق.

        يمكن تمرير الكائن المستهدَف إمّا عبر `target` (كائن ORM) — فتُشتَقّ
        بياناته تلقائياً — أو عبر `target_model` + `target_id` يدوياً.

        `field_changes` يجب أن يكون قائمة dicts بالشكل:
            [{"field": "...", "old": ..., "new": ..., "item_id": ... (اختياري)}]

        فشل الكتابة لا يُفشِل العمليّة الأصليّة (نسجّل warning ونمضي).
        """
        try:
            if target is not None:
                target_model = target_model or target.__class__.__name__
                target_id = target_id if target_id is not None else getattr(target, 'pk', None)
                if not target_repr:
                    try:
                        target_repr = str(target)[:255]
                    except Exception:
                        target_repr = ''

            actor_role = ''
            if actor is not None:
                actor_role = getattr(actor, 'role', '') or ''

            AuditLog.objects.create(
                action_type=action_type,
                actor=actor if (actor and getattr(actor, 'pk', None)) else None,
                actor_role=actor_role,
                target_model=target_model or '',
                target_id=target_id,
                target_repr=target_repr,
                qism=qism,
                field_changes=field_changes,
                reason=reason or '',
                metadata=metadata,
            )
        except Exception:
            # Audit failure must never break the main flow.
            logger.warning('فشل كتابة سجلّ التدقيق', exc_info=True)

    @staticmethod
    def log_submission_action(
        action_type, actor, submission, field_changes=None, reason='', metadata=None
    ):
        """Shortcut مخصّص لإجراءات المنجزات الأسبوعية — يملأ `qism` تلقائياً."""
        AuditService.log(
            action_type=action_type,
            actor=actor,
            target=submission,
            qism=getattr(submission, 'qism', None),
            field_changes=field_changes,
            reason=reason,
            metadata=metadata,
        )
