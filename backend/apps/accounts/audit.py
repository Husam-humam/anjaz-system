"""سجل التدقيق للعمليات الحساسة"""
import logging

audit_logger = logging.getLogger('audit')


def log_action(user, action, target_model, target_id, details=''):
    """تسجيل عملية في سجل التدقيق"""
    audit_logger.info(
        f"[AUDIT] user={user.username} (id={user.pk}, role={user.role}) "
        f"action={action} target={target_model}#{target_id} {details}"
    )
