"use client";

import { useCallback, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";
import {
  createSubmission,
  updateSubmission,
  submitSubmission,
  getPeriods,
} from "@/lib/api/submissions";
import type { WeeklySubmission, SubmissionAnswer } from "@/types/submissions";
import { STATUS_LABELS } from "@/lib/constants";

export default function SubmissionPage() {
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();
  const [submission, setSubmission] = useState<WeeklySubmission | null>(null);
  const [answers, setAnswers] = useState<Record<number, Partial<SubmissionAnswer>>>({});
  const [showConfirm, setShowConfirm] = useState(false);
  const [autoSaveTimer, setAutoSaveTimer] = useState<ReturnType<typeof setInterval> | null>(null);

  // الحصول على الفترة المفتوحة الحالية
  const { data: periodsData, isLoading: periodsLoading } = useQuery({
    queryKey: ["periods", { status: "open" }],
    queryFn: () => getPeriods({ status: "open" }),
  });

  const currentPeriod = periodsData?.results?.[0];

  // إنشاء أو استرجاع المنجز
  const createMutation = useMutation({
    mutationFn: (periodId: number) => createSubmission(periodId),
    onSuccess: (data: WeeklySubmission) => {
      setSubmission(data);
      const initialAnswers: Record<number, Partial<SubmissionAnswer>> = {};
      if (data.answers) {
        data.answers.forEach((a) => {
          initialAnswers[a.form_item] = a;
        });
      }
      setAnswers(initialAnswers);
    },
  });

  useEffect(() => {
    if (currentPeriod && !submission) {
      createMutation.mutate(currentPeriod.id);
    }
  }, [currentPeriod]);

  // حفظ الإجابات
  const saveMutation = useMutation({
    mutationFn: (data: { id: number; answers: Partial<SubmissionAnswer>[] }) =>
      updateSubmission(data.id, {
        answers: data.answers,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["submissions"] });
    },
  });

  // إرسال المنجز
  const submitMutation = useMutation({
    mutationFn: (id: number) => submitSubmission(id),
    onSuccess: (data: WeeklySubmission) => {
      setSubmission(data);
      setShowConfirm(false);
      queryClient.invalidateQueries({ queryKey: ["submissions"] });
    },
  });

  const handleSave = useCallback(() => {
    if (!submission) return;
    const answersArray = Object.values(answers).map((a) => ({
      form_item: a.form_item,
      numeric_value: a.numeric_value,
      text_value: a.text_value || "",
      is_qualitative: a.is_qualitative || false,
      qualitative_details: a.qualitative_details || "",
    }));
    saveMutation.mutate({ id: submission.id, answers: answersArray });
  }, [submission, answers]);

  // الحفظ التلقائي كل دقيقتين
  useEffect(() => {
    if (submission?.is_editable) {
      const timer = setInterval(handleSave, 120000);
      setAutoSaveTimer(timer);
      return () => clearInterval(timer);
    }
  }, [submission, handleSave]);

  const handleAnswerChange = (
    formItemId: number,
    field: string,
    value: string | number | boolean | null
  ) => {
    setAnswers((prev) => ({
      ...prev,
      [formItemId]: {
        ...prev[formItemId],
        form_item: formItemId,
        [field]: value,
      },
    }));
  };

  const handleSubmitClick = () => {
    setShowConfirm(true);
  };

  const handleConfirmSubmit = () => {
    if (!submission) return;
    handleSave();
    submitMutation.mutate(submission.id);
  };

  // حساب الوقت المتبقي
  const deadline = currentPeriod?.deadline
    ? new Date(currentPeriod.deadline)
    : null;
  const now = new Date();
  const timeRemaining = deadline ? deadline.getTime() - now.getTime() : 0;
  const hoursRemaining = Math.max(0, Math.floor(timeRemaining / (1000 * 60 * 60)));
  const showCountdown = hoursRemaining > 0 && hoursRemaining < 48;

  if (periodsLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 bg-gray-200 rounded w-64 animate-pulse" />
        <div className="bg-white rounded-xl p-6 space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!currentPeriod) {
    return (
      <div className="bg-white rounded-xl shadow-sm p-12 text-center">
        <div className="text-6xl mb-4">📅</div>
        <h2 className="text-xl font-semibold text-gray-700">
          لا يوجد أسبوع مفتوح حالياً
        </h2>
        <p className="text-gray-500 mt-2">
          يرجى الانتظار حتى يتم فتح أسبوع جديد من قبل قسم الإحصاء
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* معلومات الأسبوع */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              تقديم المنجز — الأسبوع {currentPeriod.week_number} /{" "}
              {currentPeriod.year}
            </h1>
            <p className="text-gray-500 mt-1">
              الموعد النهائي:{" "}
              {new Date(currentPeriod.deadline).toLocaleDateString("ar-IQ", {
                weekday: "long",
                year: "numeric",
                month: "long",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          </div>
          {submission && (
            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                submission.status === "draft"
                  ? "bg-gray-100 text-gray-700"
                  : submission.status === "submitted"
                  ? "bg-blue-100 text-blue-700"
                  : submission.status === "approved"
                  ? "bg-green-100 text-green-700"
                  : "bg-gray-100 text-gray-700"
              }`}
            >
              {STATUS_LABELS[submission.status]}
            </span>
          )}
        </div>

        {/* عداد تنازلي */}
        {showCountdown && (
          <div className="mt-3 bg-amber-50 border border-amber-200 text-amber-700 px-4 py-2 rounded-lg text-sm">
            ⏰ متبقي {hoursRemaining} ساعة على الموعد النهائي
          </div>
        )}
      </div>

      {/* الاستمارة */}
      {submission && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="space-y-6">
            {submission.answers?.map((answer, idx) => (
              <div
                key={answer.form_item}
                className="border-b border-gray-100 pb-5 last:border-0"
              >
                <div className="flex items-start justify-between mb-2">
                  <label className="text-sm font-medium text-gray-800">
                    {idx + 1}. {answer.indicator_name}
                    {/* سيتم تحسين هذا لاحقاً */}
                  </label>
                </div>

                {/* حقل الإدخال */}
                {answer.indicator_unit_type !== "text" ? (
                  <input
                    type="number"
                    value={
                      answers[answer.form_item]?.numeric_value ??
                      answer.numeric_value ??
                      ""
                    }
                    onChange={(e) =>
                      handleAnswerChange(
                        answer.form_item,
                        "numeric_value",
                        e.target.value ? parseFloat(e.target.value) : null
                      )
                    }
                    disabled={!submission.is_editable}
                    className="w-full max-w-xs px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none disabled:bg-gray-50"
                    dir="ltr"
                    data-testid={`answer-${idx + 1}`}
                  />
                ) : (
                  <textarea
                    value={
                      answers[answer.form_item]?.text_value ??
                      answer.text_value ??
                      ""
                    }
                    onChange={(e) =>
                      handleAnswerChange(
                        answer.form_item,
                        "text_value",
                        e.target.value
                      )
                    }
                    disabled={!submission.is_editable}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none disabled:bg-gray-50"
                    rows={2}
                  />
                )}

                {/* منجز نوعي */}
                <div className="mt-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={
                        answers[answer.form_item]?.is_qualitative ??
                        answer.is_qualitative ??
                        false
                      }
                      onChange={(e) =>
                        handleAnswerChange(
                          answer.form_item,
                          "is_qualitative",
                          e.target.checked
                        )
                      }
                      disabled={!submission.is_editable}
                      className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                      data-testid={`qualitative-${idx + 1}`}
                    />
                    <span className="text-sm text-gray-600">منجز نوعي</span>
                  </label>

                  {(answers[answer.form_item]?.is_qualitative ||
                    answer.is_qualitative) && (
                    <textarea
                      value={
                        answers[answer.form_item]?.qualitative_details ??
                        answer.qualitative_details ??
                        ""
                      }
                      onChange={(e) =>
                        handleAnswerChange(
                          answer.form_item,
                          "qualitative_details",
                          e.target.value
                        )
                      }
                      disabled={!submission.is_editable}
                      placeholder="تفاصيل المنجز النوعي *"
                      className="mt-2 w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none disabled:bg-gray-50"
                      rows={3}
                      data-testid={`qualitative-details-${idx + 1}`}
                    />
                  )}
                </div>
              </div>
            ))}

            {/* ملاحظات */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                ملاحظات إضافية
              </label>
              <textarea
                value={submission.notes}
                onChange={(e) =>
                  setSubmission({ ...submission, notes: e.target.value })
                }
                disabled={!submission.is_editable}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none disabled:bg-gray-50"
                rows={2}
              />
            </div>
          </div>

          {/* أزرار الإجراءات */}
          {submission.is_editable && (
            <div className="flex items-center justify-between mt-6 pt-6 border-t border-gray-100">
              <button
                onClick={handleSave}
                disabled={saveMutation.isPending}
                className="px-6 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition disabled:opacity-50"
              >
                {saveMutation.isPending ? "جارٍ الحفظ..." : "حفظ كمسودة"}
              </button>
              <button
                onClick={handleSubmitClick}
                disabled={submitMutation.isPending}
                className="px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:opacity-50"
              >
                {submitMutation.isPending
                  ? "جارٍ الإرسال..."
                  : "إرسال المنجز للاعتماد"}
              </button>
            </div>
          )}

          {saveMutation.isSuccess && (
            <p className="text-sm text-green-600 mt-2">
              تم حفظ المسودة بنجاح
            </p>
          )}
        </div>
      )}

      {/* مربع حوار التأكيد */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-2">تأكيد الإرسال</h3>
            <p className="text-gray-600 mb-6">
              هل أنت متأكد من إرسال المنجز الأسبوعي؟ لن تتمكن من التعديل بعد الإرسال.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                إلغاء
              </button>
              <button
                onClick={handleConfirmSubmit}
                disabled={submitMutation.isPending}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                تأكيد
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
