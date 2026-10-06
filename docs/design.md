# Design system & languages

The October 2026 redesign follows the client's mock-up: rose-pink
buttons, soft blush backgrounds, white cards with a light pink shadow,
serif display headings ("Smarter Care."), pill-shaped buttons and
chips, and a lotus logo. It is phone-first with a bottom tab bar, and
uses a top navbar on desktop. (The first version followed
`beauty_ai_final_interactive_demo.html`.)

## Layout

| | Phone (< 768px) | Desktop (≥ 768px) |
|---|---|---|
| Navigation | Bottom tab bar (`components/layout/bottom-nav.tsx`) | Top navbar with links, language switch and account, or Log in / Get Started for visitors (`components/layout/navbar.tsx`) |
| Page width | 430px column, 18px gutters (`components/layout/page.tsx`) | `wide` = 1024px (lists become 2-column grids), `narrow` = 576px (forms and flows) |
| Page title | Back arrow + centered title (`components/layout/page-header.tsx`), or a serif page heading | Same |
| Footer | Hidden (tab bar takes the space) | Shown |

The home page manages its own width: a full-width hero, then a 1152px
column. On phones it shows the logo and language switch above the hero.
`/login` and `/signup` are full-screen on phones (no tab bar).

## Navigation per role (`lib/roles.ts`)

Each kind of user sees only the screens they need. The navbar and tab bar
read the same `NAV` table, keyed by the user's `audience` from
`useAuth()`:

| Audience | Items | Lands on after login |
|---|---|---|
| Visitor / patient | Home, Doctors, AI Consultation, Appointments, Profile (visitors also get "How It Works") | `/` |
| Doctor | Dashboard, Profile | `/doctor` |
| Clinic admin | Dashboard, Appointments, Team, Profile | `/clinic` |
| Platform admin | Dashboard, Verification, Payments, Users, Profile | `/admin` |

`components/layout/role-redirect.tsx` sends staff who open a patient
screen (home, doctor search, booking, AI chat, payment…) to their own
dashboard, so doctors never see other doctors. The API still enforces
the real permissions; this only keeps each person's app uncluttered.

## Color tokens (`tailwind.config.ts`)

| Token | Value | Use |
|---|---|---|
| `bg` | `#FFF8F9` | Page background |
| `surface` | `#FFFFFF` | Cards, inputs |
| `ink` / `ink-muted` | `#2A1F2D` / `#6E6270` | Text / secondary text |
| `border` | `#F3E3E8` | Hairlines |
| `primary` | `#D6336C` | Buttons, active states (white text, 4.6:1) |
| `primary-dark` | `#B0255A` | Links, active tab, pink text on white |
| `primary-accent` | `#F06A95` | Decoration only (icons, illustrations, outlines) |
| `primary-soft` / `blush` | `#FDECF1` / `#FCE4EC` | Selected chips, icon bubbles, gradients |
| `primary-line` | `#F6B8CB` | Pink outlines and dividers |
| `lavender-soft`, `sage-soft`, `sky-soft` | `#F1E9F7`, `#E2ECE4`, `#E5EFF2` | Tile and status backgrounds |
| `sage` | `#4D6A55` | Verified badge |
| `gold` / `gold-star` | `#9A6E24` / `#BD8C39` | Rating text / star fill |

Shadows: `shadow-card` (soft pink, on cards) and `shadow-pink` (primary
buttons).

**Contrast:** the mock-up's hot pink (about `#E94B7B`) only reaches
3.6:1 with white text, which fails WCAG AA. Buttons use `#D6336C`, the
closest pink that passes (4.6:1).

## Components

`components/ui`: `Button` / `LinkButton` (primary, secondary, soft,
ghost; `sm` is a pill; `block` for full width), `Card`, `Input`,
`Badge`, `Chip` (pill filter), `SelectableCard` (single-choice rows:
clinics, payment methods), `Progress`, `Avatar` (initials, used for
patients and staff), `Notice` (blush callout), `SectionTitle`,
`EmptyState`, `ErrorState`, `Skeleton`.

Use `LinkButton` for navigation, never `<Link><Button/></Link>` (a
button inside a link is invalid HTML).

Also:

- `components/layout/logo.tsx`: `Logo` (lotus + "Beauty AI") and
  `LotusMark` (the lotus alone, also the chat assistant's icon).
- `components/doctors/doctor-avatar.tsx`: `DoctorAvatar`, eight
  illustrated doctor avatars drawn as inline SVG (`woman-1` … `woman-5`,
  two of them wearing a hijab, and `man-1` … `man-3`), plus a neutral
  default for doctors who haven't picked one. The chosen key is stored in
  `doctors.avatar`; the backend accepts only these keys
  (`AvatarKey` in `backend/app/schemas/doctor.py`).
- `components/doctors/avatar-picker.tsx`: `AvatarPicker`, used on
  doctor sign-up and the doctor dashboard.
- `components/doctors/doctor-card.tsx`: `DoctorCard`, the
  "Recommended Doctors" row: avatar, rating, clinic, next slot, price and
  a Book button.
- `components/auth/account-type-toggle.tsx`: the "I'm a Patient / I'm a
  Doctor" switch on the sign-up pages.

## Languages

- **English is the default; Arabic is a full alternative.** The switch
  is on the login screen, home screen (phones), top navbar (desktop) and
  profile.
- The choice is stored in the `locale` cookie. The root layout reads it
  on the server, so `<html lang dir>` is correct on first paint.
  There are no `/en` / `/ar` URL prefixes.
- Fonts: DM Sans for English text, Playfair Display for English
  headings (`font-display`), and Cairo for all Arabic text (neither has
  Arabic glyphs). `html[lang]` picks the fonts in `app/globals.css`.
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
