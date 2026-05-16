"""
خدمة مزامنة الهيكل التنظيمي من النظام الخارجي.

المبدأ:
- النظام الخارجي = مصدر الحقيقة للأسماء والأكواد والبنية الهرميّة وحالة النشاط
- «أنجز» = يحتفظ محلياً بالتخصيصات (PlanningAssignment / SupervisedUnit / ViewScope)
- الوحدات التي اختفت من النظام الخارجي → تُعطَّل (soft delete) ولا تُحذَف
- الوحدات اليدويّة القديمة (external_id IS NULL) → تُترك تماماً

الاستراتيجيّة:
1. جلب الشجرة الكاملة + قائمة مُسطَّحة (للحصول على unit_type_name لكل وحدة)
2. بناء خريطة external_id → بيانات الوحدة
3. تمرير ١: upsert كل الوحدات (بدون parent — لتجنّب مشاكل الترتيب)
4. تمرير ٢: ربط الـ parent لكل وحدة
5. تعطيل الوحدات التي اختفت من النظام الخارجي
6. إعادة بناء MPTT
7. إرجاع تقرير عدّاد
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.utils import timezone

from .integrations import ExternalOrgClient, ExternalOrgError
from .models import ExternalUnitTypeMapping, OrganizationUnit, UnitType

logger = logging.getLogger(__name__)


# أسماء افتراضيّة لأنواع شائعة — تُستخدم فقط لاقتراح `treat_as` عند إنشاء
# سطر جديد في `ExternalUnitTypeMapping`. الأدمن يستطيع تغييره من الواجهة.
# المصدر النهائي للحقيقة هو جدول `ExternalUnitTypeMapping` نفسه.
DEFAULT_TYPE_SUGGESTIONS: dict[str, str] = {
    'دائرة': UnitType.DAIRA,
    'مديرية': UnitType.MUDIRIYA,
    'قسم': UnitType.QISM,
    'شعبة': UnitType.QISM,
    'وحدة': UnitType.QISM,
    # مرادفات شائعة (مع الـ ال التعريف):
    'الدائرة': UnitType.DAIRA,
    'المديرية': UnitType.MUDIRIYA,
    'القسم': UnitType.QISM,
    'الشعبة': UnitType.QISM,
    'الوحدة': UnitType.QISM,
}


@dataclass
class SyncReport:
    """تقرير ما حدث في عمليّة مزامنة."""
    created: int = 0
    updated: int = 0
    deactivated: int = 0
    skipped_unknown_type: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: Any = None
    finished_at: Any = None
    dry_run: bool = False

    def summary(self) -> str:
        parts = [
            f'تمّت إضافة {self.created}',
            f'تحديث {self.updated}',
            f'تعطيل {self.deactivated}',
        ]
        if self.skipped_unknown_type:
            parts.append(f'تجاهل {self.skipped_unknown_type} (نوع غير معروف)')
        if self.errors:
            parts.append(f'{len(self.errors)} خطأ')
        if self.dry_run:
            parts.append('(تجربة فقط — لم تُطبَّق التغييرات)')
        return ' / '.join(parts)


class OrganizationSyncService:
    """
    خدمة المزامنة من النظام الخارجي.

    الاستخدام النموذجي:
        report = OrganizationSyncService().sync()
        print(report.summary())
    """

    def __init__(
        self,
        client: ExternalOrgClient | None = None,
        unit_type_map: dict[str, str | None] | None = None,
    ):
        self.client = client or ExternalOrgClient()
        # نُحمِّل الـ mapping من DB عند البَدء — يضمن أحدث القرارات من الأدمن.
        # المُختبَرون يستطيعون تمرير override يدوي.
        self.unit_type_map: dict[str, str | None] = (
            unit_type_map
            if unit_type_map is not None
            else self._load_unit_type_map_from_db()
        )

    @staticmethod
    def _load_unit_type_map_from_db() -> dict[str, str | None]:
        """
        يبني خريطة `external_type_name → treat_as` من جدول `ExternalUnitTypeMapping`.
        `treat_as=None` يعني «لم يُحدَّد بعد» — تلك الأنواع تُتجاهَل + تُعَدّ في
        skipped_unknown_type.
        """
        return dict(
            ExternalUnitTypeMapping.objects.values_list(
                'external_type_name', 'treat_as',
            )
        )

    # ─── مزامنة جدول أنواع الوحدات ─────────────

    def refresh_unit_type_mappings(self) -> dict[str, int]:
        """
        يجلب أنواع الوحدات من النظام الخارجي ويُنشئ سطراً جديداً في
        `ExternalUnitTypeMapping` لكل نوع غير معروف (مع `treat_as=NULL` أو
        اقتراح من DEFAULT_TYPE_SUGGESTIONS).

        يُرجع تقرير: {'created': N, 'existing': M}
        """
        self.client.assert_configured()
        unit_types = self.client.get_unit_types()
        created = 0
        existing = 0

        for ut in unit_types:
            name = (ut.get('name') or '').strip()
            if not name:
                continue
            suggested = DEFAULT_TYPE_SUGGESTIONS.get(name)
            obj, was_created = ExternalUnitTypeMapping.objects.get_or_create(
                external_type_name=name,
                defaults={
                    'external_type_id': ut.get('id'),
                    'treat_as': suggested,  # NULL إن لم يُعرَف
                },
            )
            if was_created:
                created += 1
            else:
                existing += 1
                # نُحدِّث الـ external_type_id إن كان مفقوداً
                if obj.external_type_id is None and ut.get('id') is not None:
                    obj.external_type_id = ut.get('id')
                    obj.save(update_fields=['external_type_id'])

        return {'created': created, 'existing': existing}

    # ─── المدخل الرئيسي ─────────────────────────

    def sync(self, dry_run: bool = False) -> SyncReport:
        """
        المدخل الرئيسي. يجلب من النظام الخارجي ويُسقط على DB المحلي.

        `dry_run=True` يحاكي العمليّة ويُرجع التقرير دون كتابة أي تغيير.
        """
        report = SyncReport(dry_run=dry_run, started_at=timezone.now())
        self.client.assert_configured()

        # 0) ضمان وجود سطر mapping لكل نوع خارجي + إعادة تحميل الخريطة
        #    (في dry_run لا نكتب، فنكتفي بالخريطة المُحمَّلة في __init__).
        if not dry_run:
            try:
                self.refresh_unit_type_mappings()
                self.unit_type_map = self._load_unit_type_map_from_db()
            except ExternalOrgError as exc:
                report.errors.append(
                    f'فشل جلب أنواع الوحدات من النظام الخارجي: {exc}'
                )
                report.finished_at = timezone.now()
                return report

        # 1) جلب البيانات الخام
        try:
            # tree للحصول على البنية الهرميّة (parent)
            tree = self.client.get_units_tree(active_only=False)
            # flat للحصول على unit_type_name (الـ tree لا يتضمّنه)
            flat_units = self._fetch_all_units_flat()
        except ExternalOrgError as exc:
            report.errors.append(f'فشل جلب البيانات من النظام الخارجي: {exc}')
            report.finished_at = timezone.now()
            return report

        # 2) دمج البيانات: external_id → {name, code, unit_type_name, parent_id, is_active}
        external_units = self._merge_tree_and_flat(tree, flat_units)
        if not external_units:
            # استجابة فارغة — نُسجّل تحذيراً ونمضي. منطق الـ deactivate سيُعطّل
            # الوحدات المحلية ذات external_id (مما يعني أن المؤسّسة الخارجيّة
            # عمليّاً فارغة). الوحدات اليدويّة (external_id IS NULL) لن تتأثّر.
            logger.warning(
                'النظام الخارجي أعاد استجابة فارغة — '
                'سيتم تعطيل أي وحدات محلية مرتبطة سابقاً.'
            )

        # 3) تنفيذ المزامنة داخل transaction
        if dry_run:
            # نُحاكي العمليّة لحساب الإحصاءات بدون كتابة
            self._simulate_sync(external_units, report)
        else:
            with transaction.atomic():
                self._apply_sync(external_units, report)
                # إعادة بناء MPTT بعد كل التعديلات (مرّة واحدة، لكفاءة أعلى)
                OrganizationUnit.objects.rebuild()

        report.finished_at = timezone.now()
        return report

    # ─── جلب البيانات المُسطَّحة (متعدّد الصفحات) ───

    def _fetch_all_units_flat(self) -> dict[int, dict[str, Any]]:
        """
        يجلب كل الوحدات بـ `detail=full` (يتطلّب التنقّل بين الصفحات).
        يُرجع dict: external_id → unit dict.
        """
        result: dict[int, dict[str, Any]] = {}
        page = 1
        page_size = 100  # حدّ النظام الخارجي

        while True:
            data = self.client.get_units_list(detail='full', page=page, page_size=page_size)
            for unit in data.get('results', []):
                ext_id = unit.get('id')
                if ext_id is not None:
                    result[int(ext_id)] = unit

            total_pages = data.get('pages', 1)
            if page >= total_pages or not data.get('results'):
                break
            page += 1

        return result

    # ─── دمج البيانات من tree + flat ───

    def _merge_tree_and_flat(
        self,
        tree: list[dict[str, Any]],
        flat: dict[int, dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        """
        يبني خريطة مُوحَّدة للوحدات. الـ tree يُعطي parent_id و children، والـ
        flat يُعطي unit_type_name و is_active وحقول أخرى.

        نُمرّر الشجرة ركيزياً (recursive) لاستخراج parent_id لكل عقدة.
        """
        merged: dict[int, dict[str, Any]] = {}

        def walk(nodes: list[dict[str, Any]], parent_id: int | None) -> None:
            for node in nodes:
                ext_id = node.get('id')
                if ext_id is None:
                    continue
                ext_id = int(ext_id)
                flat_data = flat.get(ext_id, {})
                merged[ext_id] = {
                    'external_id': ext_id,
                    'name': flat_data.get('name') or node.get('name') or '',
                    'code': flat_data.get('code') or node.get('code') or '',
                    'unit_type_name': flat_data.get('unit_type_name', ''),
                    'parent_external_id': parent_id,
                    'is_active': flat_data.get('is_active', True),
                    'employees_count': flat_data.get('employees_count', 0) or 0,
                }
                children = node.get('children') or []
                if children:
                    walk(children, parent_id=ext_id)

        walk(tree, parent_id=None)
        return merged

    # ─── تطبيق المزامنة الفعليّة ───

    def _apply_sync(
        self,
        external_units: dict[int, dict[str, Any]],
        report: SyncReport,
    ) -> None:
        """
        ينفّذ المزامنة فعلياً (داخل transaction).
        ينقسم إلى مرّتَين لتجنّب مشاكل ترتيب الـ parent.
        """
        now = timezone.now()

        # تمرير ١: upsert بدون parent (لمنع مشاكل ترتيب الـ FK)
        local_by_external: dict[int, OrganizationUnit] = {
            u.external_id: u
            for u in OrganizationUnit.objects.filter(
                external_id__in=external_units.keys()
            )
        }

        for ext_id, ext_data in external_units.items():
            mapped_type = self._resolve_treat_as(ext_data['unit_type_name'])
            if mapped_type is None:
                # treat_as = NULL (لم يُقرَّر) أو 'ignore' (قرار صريح بالتجاهل)
                # كلاهما يُتجاهَل أثناء المزامنة. نُفرّق في الـ log فقط.
                logger.warning(
                    'تجاهل وحدة: external_id=%s, type=%r (treat_as غير معرَّف أو ignore)',
                    ext_id, ext_data['unit_type_name'],
                )
                report.skipped_unknown_type += 1
                continue

            local = local_by_external.get(ext_id)
            # كل upsert في savepoint مستقل — فشل وحدة لا يكسر معاملة المزامنة
            try:
                with transaction.atomic():
                    if local is None:
                        self._create_unit(ext_id, ext_data, mapped_type, now)
                        report.created += 1
                    else:
                        if self._update_unit(local, ext_data, mapped_type, now):
                            report.updated += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception('فشل في upsert external_id=%s', ext_id)
                report.errors.append(f'وحدة {ext_id}: {exc}')

        # تمرير ٢: ربط الـ parent (الآن كل الوحدات موجودة)
        # نُعيد جلب الـ map بعد الـ creates
        local_by_external = {
            u.external_id: u
            for u in OrganizationUnit.objects.filter(
                external_id__in=external_units.keys()
            )
        }
        for ext_id, ext_data in external_units.items():
            local = local_by_external.get(ext_id)
            if not local:
                continue
            parent_ext = ext_data['parent_external_id']
            new_parent = (
                local_by_external.get(parent_ext) if parent_ext is not None else None
            )
            if local.parent_id != (new_parent.pk if new_parent else None):
                local.parent = new_parent
                # نُحدِّث parent مباشرةً عبر update لتجنّب full_clean
                # (لأن قواعد clean() القديمة قد لا تنطبق على بنية النظام الخارجي)
                OrganizationUnit.objects.filter(pk=local.pk).update(
                    parent=new_parent
                )

        # تعطيل الوحدات التي اختفت من النظام الخارجي
        # (كانت لها external_id لكن لم تَعُد في الاستجابة)
        active_ids = set(external_units.keys())
        disappeared = OrganizationUnit.objects.filter(
            external_id__isnull=False,
            is_active=True,
        ).exclude(external_id__in=active_ids)
        report.deactivated = disappeared.update(is_active=False)

    def _resolve_treat_as(self, type_name: str | None) -> str | None:
        """
        يُرجع unit_type المحلي الصحيح لاسم نوع خارجي، أو None لو وجب التجاهل.

        - النوع غير موجود في الخريطة → None (لم يُقرَّر بعد)
        - treat_as == 'ignore' → None (تجاهل صريح)
        - treat_as ∈ {daira, mudiriya, qism} → القيمة نفسها
        """
        if not type_name:
            return None
        treat_as = self.unit_type_map.get(type_name)
        if treat_as is None or treat_as == 'ignore':
            return None
        return treat_as

    def _simulate_sync(
        self,
        external_units: dict[int, dict[str, Any]],
        report: SyncReport,
    ) -> None:
        """نسخة dry-run تَعدّ الإحصاءات بدون أي كتابة."""
        local_external_ids = set(
            OrganizationUnit.objects.filter(external_id__isnull=False)
            .values_list('external_id', flat=True)
        )
        for ext_id, ext_data in external_units.items():
            mapped_type = self._resolve_treat_as(ext_data['unit_type_name'])
            if mapped_type is None:
                report.skipped_unknown_type += 1
                continue
            if ext_id in local_external_ids:
                report.updated += 1
            else:
                report.created += 1

        report.deactivated = OrganizationUnit.objects.filter(
            external_id__isnull=False, is_active=True,
        ).exclude(external_id__in=external_units.keys()).count()

    # ─── عمليّات upsert منخفضة المستوى ───

    def _create_unit(
        self,
        external_id: int,
        ext_data: dict[str, Any],
        mapped_type: str,
        now,
    ) -> OrganizationUnit:
        """
        ينشئ وحدة جديدة. نتعمّد إنشاءها بدون parent — يُربَط في التمرير
        الثاني. نتجاوز `full_clean()` المحلي لأن قواعده قد لا تنطبق
        على بنية النظام الخارجي (مثلاً مديرية مستقلّة دون دائرة أم).

        ملاحظة MPTT: نضع قيم placeholder لحقول MPTT لأن `save_base()`
        لا يستدعي منطق MPTT. القيم الصحيحة تُحسَب بـ `rebuild()` لاحقاً.
        """
        unit = OrganizationUnit(
            external_id=external_id,
            name=ext_data['name'],
            code=self._safe_code(ext_data['code'], external_id),
            unit_type=mapped_type,
            parent=None,
            is_active=ext_data.get('is_active', True),
            employees_count=ext_data.get('employees_count', 0) or 0,
            external_synced_at=now,
            # placeholders لحقول MPTT — يُعاد حسابها في rebuild()
            lft=0, rght=0, tree_id=0, level=0,
        )
        # لا نستدعي full_clean — نسمح للنظام الخارجي بقواعد بنيوية مختلفة
        # ونتجاوز MPTT save() لكي لا يُجبرنا على parent معيّن.
        unit.save_base()
        return unit

    def _safe_code(self, external_code: str | None, external_id: int) -> str:
        """
        يُرجع كود فريد. إذا كان الكود الخارجي مُستخدماً من قبل وحدة محليّة
        أخرى (يدويّة أو من sync سابق بـ id مختلف)، نُلحق `-EXT{id}` لتفاديه.
        """
        candidate = external_code or f'EXT-{external_id}'
        # نفحص فقط الوحدات التي ليست هذه نفسها (different external_id)
        conflict = OrganizationUnit.objects.filter(code=candidate).exclude(
            external_id=external_id,
        ).exists()
        if conflict:
            candidate = f'{candidate}-EXT{external_id}'
        return candidate

    def _update_unit(
        self,
        local: OrganizationUnit,
        ext_data: dict[str, Any],
        mapped_type: str,
        now,
    ) -> bool:
        """
        يُحدِّث وحدة موجودة. يُرجع True إذا تغيّر شيء فعلاً.
        لا يلمس أي حقل محلي خاص (التخصيصات تبقى كما هي).
        """
        new_code = self._safe_code(ext_data['code'], local.external_id)
        new_employees_count = ext_data.get('employees_count', 0) or 0
        changed = (
            local.name != ext_data['name']
            or local.code != new_code
            or local.unit_type != mapped_type
            or local.is_active != ext_data.get('is_active', True)
            or local.employees_count != new_employees_count
        )

        local.name = ext_data['name']
        local.code = new_code
        local.unit_type = mapped_type
        local.is_active = ext_data.get('is_active', True)
        local.employees_count = new_employees_count
        local.external_synced_at = now

        OrganizationUnit.objects.filter(pk=local.pk).update(
            name=local.name,
            code=local.code,
            unit_type=local.unit_type,
            is_active=local.is_active,
            employees_count=local.employees_count,
            external_synced_at=local.external_synced_at,
        )
        return changed
