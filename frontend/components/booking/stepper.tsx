import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Numbered step indicator. The design brief explicitly warns against
 * decorative 01/02/03 markers — this is the one place in the app where
 * the content genuinely IS a sequence (a booking wizard), so numbering
 * is earned here, not decorative.
 */
export function Stepper({ steps, currentStep }: { steps: string[]; currentStep: number }) {
  return (
    <ol className="flex items-center gap-2 overflow-x-auto pb-2">
      {steps.map((label, index) => {
        const stepNumber = index + 1;
        const isDone = stepNumber < currentStep;
        const isCurrent = stepNumber === currentStep;
        return (
          <li key={label} className="flex shrink-0 items-center gap-2">
            <span
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold",
                isDone && "bg-sage text-white",
                isCurrent && "bg-primary text-white",
                !isDone && !isCurrent && "bg-border text-ink-muted"
              )}
            >
              {isDone ? <Check className="h-4 w-4" /> : stepNumber}
            </span>
            <span className={cn("text-sm", isCurrent ? "font-semibold text-ink" : "text-ink-muted")}>
              {label}
            </span>
            {stepNumber < steps.length && <span className="mx-1 h-px w-6 bg-border" />}
          </li>
        );
      })}
    </ol>
  );
}
