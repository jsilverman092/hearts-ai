# UI Aesthetics Plan

Goal: improve visual polish without touching any game logic or DOM structure.
All changes are CSS-only unless noted. JS is untouched. HTML changes are cosmetic attributes only (e.g. adding a `<span>` for a suit watermark in the hero).

---

## 1. Typography upgrade

**Problem:** System fonts (Trebuchet MS, Cambria, Consolas) look dated and render inconsistently across platforms.

**Fix:** Add a single `<link>` to Google Fonts in `<head>` and remap the three font variables.

Suggested stack:
- Display/headings → **Playfair Display** (elegant serif, suits a card game theme)
- Body text → **Lato** or **Source Serif 4** (readable, warm)
- Mono → **JetBrains Mono** (sharper digits for scores/codes)

```html
<!-- index.html <head> addition -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Lato:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
```

Then in `:root`:
```css
--display: "Playfair Display", Georgia, serif;
--text:    "Lato", system-ui, sans-serif;
--mono:    "JetBrains Mono", "Consolas", monospace;
```

---

## 2. Hero section refinement

**Problem:** The header is plain — just stacked text with no visual anchor.

**Fix:**
- Add a subtle decorative suit row (♣ ♦ ♠ ♥) below the kicker as a pure HTML/CSS element, colored with suit-appropriate tones and a slight opacity.
- Increase the kicker letter-spacing to feel more like a label stamp.
- Give the `h1` a faint text-shadow for depth.

```html
<!-- New line after .kicker in index.html -->
<p class="suit-row" aria-hidden="true">♣ &diams; ♠ &hearts;</p>
```

```css
.kicker { letter-spacing: 0.22em; }

.hero h1 { text-shadow: 0 1px 0 rgba(255,255,255,0.55); }

.suit-row {
  margin: 0.3rem 0 0;
  font-size: 1.1rem;
  letter-spacing: 0.35em;
  color: var(--accent);
  opacity: 0.45;
}
.suit-row:nth-child(odd) { color: var(--accent-2); } /* red suits */
```

---

## 3. Panel & card depth

**Problem:** Panels look flat — the border and shadow are subtle but there's no sense of layering.

**Fix:**
- Increase panel shadow slightly and add a thin inset highlight on the top edge.
- Round the `.card` radius from 12px → 14px to match `.panel`.
- Add a `backdrop-filter: blur(6px)` bump on wider screens.

```css
.panel {
  box-shadow:
    0 1px 0 rgba(255,255,255,0.65) inset,
    0 10px 24px rgba(35, 31, 22, 0.13);
  backdrop-filter: blur(6px);
}

.card {
  border-radius: 14px;
  box-shadow: 0 1px 0 rgba(255,255,255,0.55) inset;
}
```

---

## 4. Button polish

**Problem:** Buttons have a minimal hover (translateY + saturate) that feels lightweight. No focus ring, no pressed state.

**Fix:**
- Add a proper `:focus-visible` ring using the accent color.
- Add an `:active` press effect (scale down slightly).
- Give `.action` buttons a subtle gradient overlay for depth.
- Give `.ghost` buttons a semi-transparent background on hover.

```css
button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

button:active:not(:disabled) {
  transform: translateY(0) scale(0.97);
  filter: brightness(0.95);
}

.action {
  background: linear-gradient(175deg, color-mix(in srgb, var(--accent) 88%, white), var(--accent));
}

.action.alt {
  background: linear-gradient(175deg, color-mix(in srgb, var(--accent-2) 88%, white), var(--accent-2));
}

.ghost:hover:not(:disabled) {
  background: rgba(35, 33, 30, 0.06);
}
```

---

## 5. Input refinement

**Problem:** Inputs have a slight background (#fffef8) but no focus treatment, so they look dead until typed into.

**Fix:**
- Add a focus style with accent-color ring.
- Subtle transition on border color.

```css
input {
  transition: border-color 140ms ease, box-shadow 140ms ease;
}

input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(10, 106, 63, 0.14);
}
```

---

## 6. Status line visual upgrade

**Problem:** The status line looks like a utility row — functional but plain.

**Fix:**
- Add a left border accent on each status cell.
- Make the `.badge` for the connected state pulse gently with a CSS animation.

```css
.status-line > div {
  border-left: 2px solid var(--line);
  padding-left: 0.62rem;
}

.badge:not(.muted) {
  animation: pulse-badge 2.4s ease-in-out infinite;
}

@keyframes pulse-badge {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.72; }
}
```

---

## 7. Playing card polish

**Problem:** Cards are minimal white rectangles — functional but not premium-feeling.

**Fix:**
- Add a very subtle inner border/highlight to simulate card stock.
- Add a micro paper-texture background using a CSS gradient (no image needed).
- Slightly enlarge the center suit symbol.
- Add a gentle lift shadow on `.card-btn:hover .playing-card`.

```css
.playing-card {
  background:
    linear-gradient(135deg, rgba(255,255,255,0.9), rgba(248,246,240,0.95));
  box-shadow:
    0 0 0 1px rgba(200,190,172,0.6) inset,
    0 2px 6px rgba(23, 20, 17, 0.18);
}

.playing-card .suit {
  font-size: 1.35rem; /* was 1.18rem */
}

.card-btn:hover:not(:disabled) .playing-card {
  transform: translateY(-2px);
  box-shadow:
    0 0 0 1px rgba(200,190,172,0.6) inset,
    0 5px 12px rgba(23, 20, 17, 0.22);
}
```

---

## 8. Card buttons — legal/selected states

**Problem:** Legal cards have only a green border. Selected (pass) cards have only a rust border + faint background. The distinction is subtle and easy to miss.

**Fix:**
- Legal cards: add a soft green top-edge glow.
- Selected cards: add a stronger tint and a checkmark or slight scale-up.
- Play-ready cards: add a more obvious call-to-action feel.

```css
.card-btn.legal {
  border-color: rgba(10, 106, 63, 0.82);
  box-shadow: 0 -2px 0 rgba(10, 106, 63, 0.6) inset;
}

.card-btn.selected {
  border-color: rgba(162, 75, 45, 0.9);
  background: rgba(162, 75, 45, 0.14);
  transform: translateY(-3px);
}

.card-btn.play:hover:not(:disabled) {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(10, 106, 63, 0.25);
}
```

---

## 9. Table felt enhancement

**Problem:** The felt surface looks good but a bit uniform. A real card table has some texture and a visible rim.

**Fix:**
- Add a subtle repeating CSS texture using radial gradients (no image).
- Deepen the inset shadow at the edges.
- Add a thin "rim" ring just inside the border.

```css
.table-surface {
  background:
    radial-gradient(circle at 45% 40%, rgba(38, 128, 80, 0.45), rgba(20, 80, 52, 0.85)),
    repeating-radial-gradient(circle at 50% 50%, transparent 0, transparent 3px, rgba(0,0,0,0.015) 3px, rgba(0,0,0,0.015) 4px),
    linear-gradient(160deg, var(--felt0), var(--felt1));
  box-shadow:
    inset 0 0 0 4px rgba(255,255,255,0.07),
    inset 0 0 0 5px rgba(0,0,0,0.18),
    inset 0 18px 40px rgba(0,0,0,0.28),
    inset 0 -8px 20px rgba(0,0,0,0.15);
}
```

---

## 10. Seat card polish

**Problem:** Seat cards blend into the felt and don't clearly distinguish player types (you vs bot vs open).

**Fix:**
- "You" seat: warmer gold tint on background, not just border.
- Active seat: brighter border + a pulsing glow animation.
- Open seat: dashed border to signal "available".

```css
.table-seat.you {
  background: rgba(15, 55, 35, 0.72);
  border-color: rgba(255, 223, 163, 0.85);
  box-shadow: 0 0 0 2px rgba(255, 223, 163, 0.25), 0 4px 12px rgba(0,0,0,0.3);
}

.table-seat.active {
  border-color: rgba(171, 237, 203, 0.95);
  box-shadow: 0 0 0 2px rgba(171, 237, 203, 0.28);
  animation: active-pulse 1.6s ease-in-out infinite;
}

@keyframes active-pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(171, 237, 203, 0.28); }
  50%       { box-shadow: 0 0 0 4px rgba(171, 237, 203, 0.45); }
}

.table-seat.open {
  border-style: dashed;
  border-color: rgba(200, 200, 190, 0.4);
}
```

---

## 11. Trick grid animation

**Problem:** The `trick-card-in` animation is minimal (5px translateY + opacity). Cards appear but don't feel "played".

**Fix:**
- Animate from a slightly larger starting scale and a more pronounced drop.
- Keep duration short so it doesn't slow gameplay feel.

```css
@keyframes trick-card-in {
  from {
    transform: translateY(-6px) scale(1.06);
    opacity: 0;
  }
  to {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
}
```

---

## 12. Pace card layout tweak

**Problem:** The pace grid uses `repeat(2, minmax(140px, 1fr))` which causes the speed label and range input to split across columns awkwardly.

**Fix:** No layout change (that would risk functionality), but style the range input thumb and track to match the color scheme.

```css
input[type="range"] {
  accent-color: var(--accent);
}
```

---

## Implementation order

1. Google Fonts link (index.html, 2 lines)
2. Font variable remaps (styles.css :root)
3. Button polish — focus, active, gradients
4. Input focus states
5. Panel/card depth (shadow + inset)
6. Status line left-border + badge pulse
7. Playing card polish
8. Legal/selected card states
9. Felt surface enhancement
10. Seat card differentiation
11. Trick animation update
12. Hero suit-row decoration (index.html + CSS)
13. Range input accent-color

Each step is independently testable and reversible.
