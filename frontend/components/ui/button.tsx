import Link, { type LinkProps } from "next/link";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type AnchorHTMLAttributes, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 font-bold transition-colors disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-primary text-white hover:bg-primary-dark",
        secondary: "border border-primary-line bg-surface text-primary-dark hover:bg-primary-soft",
        soft: "bg-primary-soft text-primary-dark hover:bg-primary-soft/70",
        ghost: "bg-transparent text-ink hover:bg-primary-soft/60",
      },
      size: {
        sm: "h-9 rounded-xl px-4 text-sm",
        md: "h-12 rounded-[14px] px-6 text-[15px]",
      },
      block: { true: "w-full" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

type Variants = VariantProps<typeof buttonVariants>;

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, Variants {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, block, type = "button", ...props }, ref) => (
    <button ref={ref} type={type} className={cn(buttonVariants({ variant, size, block }), className)} {...props} />
  )
);
Button.displayName = "Button";

/**
 * A link styled as a button. Use this instead of wrapping <Button> in
 * <Link> — a <button> inside an <a> is invalid HTML and confuses
 * keyboard and screen-reader users.
 */
export function LinkButton({
  className,
  variant,
  size,
  block,
  ...props
}: LinkProps & AnchorHTMLAttributes<HTMLAnchorElement> & Variants) {
  return <Link className={cn(buttonVariants({ variant, size, block }), className)} {...props} />;
}
