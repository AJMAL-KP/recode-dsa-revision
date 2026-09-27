# ReCode - Spaced Repetition DSA Revision Assistant

A spaced-repetition revision assistant for DSA problems. Helps developers retain algorithmic patterns, recognition cues, mistakes, and personal observations through active recall and adaptive FSRS scheduling.

---

## 🎨 UI Design System & Guidelines
The design system and UI contracts are formally defined in [.agents/rules/ui-theme-spec.md](file:///.agents/rules/ui-theme-spec.md).

- **Theme**: Dark-first obsidian aesthetic (`#0b0f17` background, `#101623` cards, `#182030` surfaces).
- **Accents**: Brand LeetCode orange (`#ea580c` / `#f97316`) with `border-white/10` borders.
- **Typography**: Plus Jakarta Sans (`font-sans`) and JetBrains Mono (`font-mono`).

---

## 🔐 Authentication Architecture
- **Credentials**: Email & Password strictly used for authentication.
- **Display Name**: Collected during signup solely for greetings and visual display.
- **Backend**: Custom `EmailBackend` supporting case-insensitive email matching.
- **User Model**: Custom `core.User` extending `AbstractBaseUser` and `PermissionsMixin`.
- **Validation**:
  - Submit-first validation (no premature red errors on typing/focusing).
  - Native HTML popups disabled via `novalidate`; all errors display inline in orange text.
  - Sensitive inputs (`password`, `confirm_password`) are zeroed out on failed submissions.
  - Non-sensitive inputs (`name`, `email`) are preserved across failed submissions.
  - Post-Redirect-Get (PRG) pattern prevents "Confirm Form Resubmission" browser prompts.
- **Cache Control**: `@never_cache` prevents back-button exposure for authenticated routes.