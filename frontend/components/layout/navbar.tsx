"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X, Sparkles, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePatientContext } from "@/lib/patient-context";

const NAV_LINKS = [
  { href: "/doctors", label: "الأطباء" },
  { href: "/clinics", label: "العيادات" },
  { href: "/procedures", label: "الإجراءات" },
  { href: "/consultation", label: "اسألي BeautyAI" },
];

export function Navbar() {
  const [open, setOpen] = useState(false);
  const { patient } = usePatientContext();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-bg/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 md:px-6">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold text-ink">
          <Sparkles className="h-5 w-5 text-primary" strokeWidth={1.75} />
          BeautyAI
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          {NAV_LINKS.map((link) => (
            <Link key={link.href} href={link.href} className="text-sm font-medium text-ink-muted hover:text-ink">
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          {patient ? (
            <Link
              href="/account"
              className="flex items-center gap-2 rounded-full border border-border px-4 py-2 text-sm font-medium text-ink hover:bg-surface"
            >
              <User className="h-4 w-4" />
              {patient.full_name.split(" ")[0]}
            </Link>
          ) : (
            <Link href="/login" className="text-sm font-medium text-ink-muted hover:text-ink">
              تسجيل الدخول
            </Link>
          )}
          <Link href="/booking">
            <Button size="sm">احجزي موعدك</Button>
          </Link>
        </div>

        <button
          type="button"
          className="p-2 md:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "إغلاق القائمة" : "فتح القائمة"}
        >
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {open && (
        <nav className="flex flex-col gap-1 border-t border-border bg-bg px-4 py-4 md:hidden">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-lg px-3 py-2 text-sm font-medium text-ink hover:bg-surface"
              onClick={() => setOpen(false)}
            >
              {link.label}
            </Link>
          ))}
          <div className="mt-2 flex flex-col gap-2 border-t border-border pt-3">
            <Link
              href={patient ? "/account" : "/login"}
              className="rounded-lg px-3 py-2 text-sm font-medium text-ink hover:bg-surface"
              onClick={() => setOpen(false)}
            >
              {patient ? "حسابي" : "تسجيل الدخول"}
            </Link>
            <Link href="/booking" onClick={() => setOpen(false)}>
              <Button size="sm" className="w-full">احجزي موعدك</Button>
            </Link>
          </div>
        </nav>
      )}
    </header>
  );
}
