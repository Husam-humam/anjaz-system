import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { AxiosError } from "axios";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * تنسيق موحّد للأرقام — يستخدم الأرقام اللاتينية مع فواصل الآلاف.
 * السبب: الأرقام الهندية (العربية-الهندية) تسبّب ازدواجية غير موحّدة في الـ BI،
 * والأرقام اللاتينية مع الفواصل هي المعيار المهني الأوضح للقراءة.
 *
 * formatNumber(1234567) → "1,234,567"
 * formatNumber(85.5) → "85.5"
 * formatNumber(null) → "—"
 */
export function formatNumber(
  value: number | null | undefined,
  options: { decimals?: number; fallback?: string } = {}
): string {
  const { decimals, fallback = "—" } = options;
  if (value === null || value === undefined || Number.isNaN(value)) {
    return fallback;
  }
  if (decimals !== undefined) {
    return value.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }
  // عرض ذكي: لا نعرض فواصل عشرية للأعداد الصحيحة
  if (Number.isInteger(value)) {
    return value.toLocaleString("en-US");
  }
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

/** تنسيق نسبة مئوية — "85.5%" */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${formatNumber(value, { decimals: value % 1 === 0 ? 0 : 1 })}%`;
}

/**
 * استخراج رسالة خطأ مقروءة من استجابة axios.
 * يدعم تنسيقات الـ backend المختلفة:
 *  - { error, message, code, details } — التنسيق الموحّد من anjaz
 *  - { detail: "..." } — تنسيق DRF الافتراضي
 *  - { field_name: ["..."] } — أخطاء serializer الحقلية
 *  - أي رسالة نصية أخرى
 *
 * الأولوية: أخطاء details الحقلية المفصّلة > message العام > detail > fallback
 */
function extractFirstFieldError(obj: Record<string, unknown>): string | null {
  for (const [key, value] of Object.entries(obj)) {
    if (key === "non_field_errors" || key === "detail" || key === "message") continue;
    if (Array.isArray(value) && value.length > 0) {
      if (typeof value[0] === "string") return value[0];
      if (typeof value[0] === "object" && value[0] !== null) {
        const nested = extractFirstFieldError(value[0] as Record<string, unknown>);
        if (nested) return nested;
      }
    } else if (typeof value === "string") {
      return value;
    } else if (value && typeof value === "object") {
      const nested = extractFirstFieldError(value as Record<string, unknown>);
      if (nested) return nested;
    }
  }
  return null;
}

export function getErrorMessage(error: unknown, fallback = "حدث خطأ غير متوقع"): string {
  if (error instanceof AxiosError) {
    const data = error.response?.data;
    if (data && typeof data === "object") {
      const d = data as Record<string, unknown>;

      // 1) إذا كان هناك details غير فارغ — استخرج أول خطأ حقلي مفصّل (أولوية قصوى)
      if (d.details && typeof d.details === "object" && d.details !== null) {
        const specific = extractFirstFieldError(
          d.details as Record<string, unknown>
        );
        if (specific) return specific;
        // أو non_field_errors داخل details
        const nfe = (d.details as Record<string, unknown>).non_field_errors;
        if (Array.isArray(nfe) && typeof nfe[0] === "string") return nfe[0] as string;
      }

      // 2) non_field_errors على المستوى الأعلى
      if (Array.isArray(d.non_field_errors) && typeof d.non_field_errors[0] === "string") {
        return d.non_field_errors[0] as string;
      }

      // 3) خطأ حقل مباشر على المستوى الأعلى
      const topLevelFieldError = extractFirstFieldError(d);
      if (topLevelFieldError) return topLevelFieldError;

      // 4) message العام (قد يكون "بيانات غير صالحة" الافتراضي)
      if (typeof d.message === "string") return d.message;

      // 5) detail من DRF
      if (typeof d.detail === "string") return d.detail;
    }
    if (error.message) return error.message;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("ar-IQ", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("ar-IQ", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
