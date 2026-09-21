# Design system & languages

The frontend follows the approved interactive demo
(`beauty_ai_final_interactive_demo.html`): a soft pink / lavender / sage
palette, white 18px-radius cards, a phone-first layout with a bottom tab
bar, and a desktop layout with a top navbar.

## Layout

| | Phone (< 768px) | Desktop (≥ 768px) |
|---|---|---|
| Navigation | Bottom tab bar: Home, Appointments, Consult, Profile (`components/layout/bottom-nav.tsx`) | Top navbar with links, language switch, account, "Book now" (`components/layout/navbar.tsx`) |
| Page width | 430px column, 18px gutters (`components/layout/page.tsx`) | `wide` = 1024px (lists become 2-column grids), `narrow` = 576px (forms and flows) |
| Page title | Back arrow + centered title (`components/layout/page-header.tsx`) | Same |
| Footer | Hidden (tab bar takes the space) | Shown |

`/login` and `/signup` are full-screen on phones (no tab bar), as in the demo.

## Color tokens (`tailwind.config.ts`)

| Token | Value | Use |
|---|---|---|
| `bg` | `#FBF7F5` | Page background |
| `surface` | `#FFFFFF` | Cards, inputs |
| `ink` / `ink-muted` | `#322D32` / `#6F676C` | Text / secondary text |
| `border` | `#EEE7E5` | Hairlines |
| `primary` | `#B9546B` | Buttons, selected date/time (white text, 4.6:1) |
| `primary-dark` | `#9E4459` | Links, active tab, icons on soft pink |
| `primary-accent` | `#E98DA0` | The demo's pink: decoration only (progress fill, selected outlines, logo) |
| `primary-soft` | `#F8E4E8` | Selected cards, avatars |
| `lavender-soft`, `sage-soft`, `sky-soft` | `#E9E3F3`, `#E2ECE4`, `#E5EFF2` | Tile and icon backgrounds |
| `sage` | `#4D6A55` | Verified badge, clinic icons |
| `gold` / `gold-star` | `#9A6E24` / `#BD8C39` | Rating text / star fill |

**Contrast change from the demo:** the demo puts white text on
`#e98da0`, which is only 2.4:1 and fails WCAG AA. Buttons therefore use
the darker `primary`; the demo pink is kept for non-text decoration.
The demo's grey text (`#8f878c`, 3.3:1) is darkened to `#6F676C` (5.2:1).

## Components (`components/ui`)

`Button` / `LinkButton` (primary, secondary, soft, ghost; `block` for
full width), `Card`, `Input`, `Badge`, `Chip` (filter), `SelectableCard`
(single-choice rows: clinics, payment methods), `Progress`, `Avatar`
(initials — no stock photos or gendered emoji for real providers),
`Notice` (lavender callout), `SectionTitle`, `EmptyState`, `ErrorState`,
`Skeleton`.

Use `LinkButton` for navigation, never `<Link><Button/></Link>` (a
button inside a link is invalid HTML).

## Languages

- **English is the default; Arabic is a full alternative.** The switch
  is on the login screen, home screen (phones), top navbar (desktop) and
  profile.
- The choice is stored in the `locale` cookie. The root layout reads it
  on the server, so `<html lang dir>` is correct on first paint.
  There are no `/en` / `/ar` URL prefixes.
- Fonts: DM Sans for English, Cairo for Arabic (DM Sans has no Arabic
  glyphs). `html[lang]` picks the font in `app/globals.css`.
- Strings live in `lib/i18n/messages/en.ts` (source of truth) and
  `ar.ts`. `ar.ts` is typed against the English shape, so a missing
  Arabic string fails `npm run type-check`.
- In components: `const { t, label, formatDate, formatTime, formatCurrency } = useI18n()`.
  - `t("booking.title")`, with `{placeholders}`: `t("doctors.years", { count: 8 })`.
  - `label("specialties", doctor.specialty)` translates a raw backend
    value and falls back to the value itself when there's no entry.
  - Dates, times and numbers use `Intl` (`en-US` / `ar-EG`).
- RTL: use logical utilities (`ms-`, `ps-`, `start-`, `text-start`) and
  `rtl:rotate-180` for directional icons (chevrons). Phone numbers and
  emails are wrapped in `dir="ltr"`.
- Arabic copy addresses the patient in the feminine form, matching the
  product's primary audience and the copy before the redesign.

### Known gap

Database content (doctor names, bios, clinic and procedure names) is
stored in one language only. Showing it in both languages needs
bilingual fields — planned with the Sprint 5 schema changes.
