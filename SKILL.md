# Frontend Designer Skill (PnL App)

Use this skill when designing or implementing frontend UI for this project.

## Goal

Create a native Apple-like dashboard experience:
- Dark mode is default.
- Light mode is available in Settings.
- Motion should feel iOS-like: smooth, purposeful, and hierarchy-driven.
- Preserve existing app structure where it already matches product behavior.

## When To Trigger

Use this skill for:
- Dashboard redesigns or visual polish
- New views/components that affect look and feel
- Theme, motion, typography, spacing, and interaction updates

## Hard Rules

- This product is a dashboard, so ignore the "one composition only" landing-page rule.
- Brand should still be clearly present and recognizable in the top viewport.
- No generic, overbuilt layouts.
- Typography must be intentional and Apple-native in feel.
- Backgrounds should have depth (gradients, texture, subtle layers), not flat filler.
- Avoid cards by default; use them only when they improve interaction clarity.
- One job per section: one purpose, one headline, one supporting sentence max.
- Reduce clutter: avoid stat-strip spam, dense chip clusters, and competing callouts.
- Use motion to establish hierarchy and context, not decoration.
- Ship at least 2-3 intentional motions for visually led screens.
- Keep desktop and mobile behavior first-class.
- No purple bias in palette choices.

## Apple-Native Visual Direction

- Prefer SF Pro Display/Text where available, with clean fallbacks.
- Use high-quality blur/translucency, layered depth, and restrained contrast.
- Favor rounded geometry, refined spacing rhythm, and minimal chrome.
- Interactions should feel tactile and direct (not "web toy" animation).

## Theme System Requirements

- Default theme is `dark`.
- Provide `light` mode in Settings via explicit user toggle.
- Persist theme choice (local storage or server preference based on app architecture).
- On first load with no stored choice, default to dark.
- Define theme tokens using CSS variables for both themes.
- Ensure all key surfaces/components have both dark and light token mappings.

## Motion Requirements

Include at least 2-3 of the following with polished timing:
- Staggered content entrance on page load
- Smooth panel/modal transitions with opacity + subtle transform
- Selection/toggle transitions for charts/filters/tabs
- Navigation transitions that preserve spatial continuity

Animation guidance:
- Use eased curves resembling iOS motion (gentle accelerate/decelerate).
- Keep durations short to medium; avoid bouncy or exaggerated effects.
- Respect reduced-motion preferences.

## React Implementation Guidance

- Follow existing repo patterns first.
- Prefer modern React patterns (`useEffectEvent`, `startTransition`, `useDeferredValue`) when appropriate and aligned with team usage.
- Do not add `useMemo`/`useCallback` by default unless the existing codebase already uses them for a clear reason.

## Output Checklist

Every frontend change should include:
- Theme behavior: dark default + light in settings verified
- Visual consistency across dashboard surfaces
- Motion list: what was added and why
- Desktop/mobile verification notes
- Accessibility sanity checks (contrast, focus states, reduced motion)

## Exception Rule

If a local design system or established product pattern already exists, preserve it and evolve it rather than replacing it blindly.
