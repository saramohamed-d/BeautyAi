"use client";

import { useHealth } from "@/hooks/use-health";
import { StatusBadge } from "@/components/status-badge";

/**
 * Landing page — Sprint 0 placeholder.
 *
 * This intentionally does real work (calls the live backend /health
 * endpoint) rather than being static filler. It proves, end-to-end, that:
 *   - Next.js can reach FastAPI over HTTP (CORS is configured correctly)
 *   - TanStack Query + the service/hook layers are wired correctly
 *   - RTL layout renders correctly with Arabic placeholder copy
 *
 * The real landing page (hero, CTA into /chat, doctor highlights, etc.)
 * is out of scope until later sprints — see roadmap.
 */
export default function HomePage() {
  const { data, isLoading, isError, error } = useHealth();

  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col items-center justify-center gap-6 px-6 text-center">
      <h1 className="text-3xl font-bold">بيوتي AI</h1>
      <p className="text-gray-600">
        منصة ذكاء اصطناعي لربط المرضى بأطباء وعيادات التجميل والجلدية المعتمدة.
      </p>

      <div className="w-full rounded-xl border border-gray-200 p-4 text-start">
        <h2 className="mb-3 text-sm font-semibold text-gray-500">حالة النظام (Backend Health)</h2>

        {isLoading && <p className="text-sm text-gray-500">جاري التحقق من حالة الخادم...</p>}

        {isError && (
          <p className="text-sm text-red-600">
            تعذر الاتصال بالخادم: {error instanceof Error ? error.message : "خطأ غير معروف"}
          </p>
        )}

        {data && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">الحالة العامة</span>
              <StatusBadge status={data.status} label={data.status} />
            </div>
            {data.components.map((component) => (
              <div key={component.name} className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{component.name}</span>
                <StatusBadge status={component.status} label={component.status} />
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
