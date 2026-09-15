import Link from "next/link";
import { Sparkles, Stethoscope } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * "Ask BeautyAI" entry point — UI PLACEHOLDER ONLY.
 *
 * Per the Sprint 3 brief: no AI agent, no OpenAI calls, no medical logic
 * here. This page exists so the product's navigation and information
 * architecture already has the right entry point for the AI-assisted
 * booking experience that arrives in a future sprint (Sprint 5+:
 * LangGraph, Intake Agent, Safety Agent). Building the entry point now
 * means Sprint 5+ only needs to replace this page's content, not
 * restructure navigation across the app.
 */
export default function ConsultationPage() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center gap-4 px-4 py-16 text-center md:px-6">
      <Sparkles className="h-10 w-10 text-primary" strokeWidth={1.5} />
      <h1 className="text-2xl font-bold text-ink md:text-3xl">اسألي BeautyAI</h1>
      <p className="text-ink-muted">
        مساعدة الذكاء الاصطناعي لاختيار الطبيب والإجراء المناسب لك قريباً. في الوقت الحالي، يمكنك تصفّح
        الأطباء والإجراءات مباشرة والحجز بسهولة.
      </p>
      <div className="mt-2 flex flex-wrap justify-center gap-3">
        <Link href="/doctors">
          <Button>
            <Stethoscope className="h-4 w-4" />
            تصفّحي الأطباء
          </Button>
        </Link>
        <Link href="/procedures">
          <Button variant="outline">استكشفي الإجراءات</Button>
        </Link>
      </div>
    </div>
  );
}
