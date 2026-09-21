import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

const widths = {
  narrow: "md:max-w-xl",
  wide: "md:max-w-5xl",
};

/**
 * Page container. On phones every page is the demo's 430px column with
 * room at the bottom for the tab bar; on desktop it widens so lists can
 * become grids. `narrow` suits forms and single-item flows.
 */
export function Page({ children, width = "wide", className }: { children: ReactNode; width?: keyof typeof widths; className?: string }) {
  return (
    <div className={cn("mx-auto w-full max-w-[430px] px-[18px] pb-28 pt-5 md:pb-16 md:pt-10", widths[width], className)}>
      {children}
    </div>
  );
}
