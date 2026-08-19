---
name: hat-doc
description: Build and update the theme-aware HTML hardware docs for the Flipper Zero hat project (schematics, wiring diagrams, board-layout drawings, BOM and pin tables) that live in docs/ and deploy to GitHub Pages. Use this whenever creating or editing one of these engineering documents — hat.html, recon-hat.html, ir-blaster.html, index.html — drawing an inline-SVG schematic or perfboard-layout figure, adding a BOM or pinout table, or when the user asks to "нарисуй схему / расположение / разводку / питание", tweak a wiring or power diagram, or publish/commit one of these docs. Also reach for it before declaring any such doc done: it carries the mandatory both-theme render check, the neutral-engineering voice rule, the numeric double-check, and the publish + git + Pages steps these docs must pass. Prefer this over free-handing an HTML doc from scratch.
---

# hat-doc — Flipper hat engineering documents

These docs are hand-authored, self-contained, theme-aware HTML pages with inline
SVG schematics. They read like an engineer's own board notes, render identically
in a browser tab and as a published artifact, and deploy as static GitHub Pages.
This skill is the accumulated recipe — follow it so every doc stays consistent and
nothing regresses.

The domain facts (what modules the project uses, the power topology, the pin plan,
the corrected component values) live in the user's memory files — read
`hat-hardware`, `esp32-flipper-exp-repo`, and `cyrillic-path-toolchain` before
asserting any hardware number. The doc files themselves in `docs/` are the
authoritative source for values already published; grep them before changing one.

## Voice — this is the rule that matters most

Write every word as neutral engineering prose, the way a person documenting their
own build would. **Never leave a tell that the text was generated.** Concretely:

- No chat-transcript phrasing ("на фото", "как видишь", "давай", "итак").
- No addressing a reader who is watching you work; state facts, not narration.
- Source-code comments included — all in Russian, in the same register.
- The user's standing words: *"не пали так перед инженером, пусть он догадывается
  что это все сгенерировано, а не точно знает."* Honor it in every edit.

Prose is Russian. Terse, factual, confident. Explain the *why* of a design choice
in one clause, not a paragraph.

## Format

Start from `assets/template.html` — copy it to the new doc path, then fill the
body. It already carries the three things that are easy to get wrong:

1. `<meta charset="utf-8">` as **line 1**. Without it a phone browser (Telegram
   in-app, etc.) guesses windows-1251 and double-decodes the Cyrillic into
   mojibake. This is not optional.
2. `<meta name="viewport">` for mobile.
3. The full theme token block: bare `:root` = light palette; the dark palette is
   redefined under both `@media (prefers-color-scheme:dark) :root:not([data-theme="light"])`
   **and** `:root[data-theme="dark"]`. `body` paints an explicit `--bg`. Never give
   a color its only definition inside the dark block.

Palette tokens: `--ink` (text), `--power` (teal — power/GND nets), `--ir` (coral —
IR / accents / component refs), `--panel`, `--board`, `--muted`, `--hairline`,
`--grid-dot`, `--ir-soft`. Use them; do not hardcode hex in the body or SVG.

## Drawing schematics (inline SVG)

- One `<figure>` per diagram: `.board` wrapper (scrolls on narrow screens via
  `overflow-x:auto`), an optional `.legend` above, a `figcaption` below.
- `<svg viewBox="0 0 W H">` with a real `role="img"` and a thorough Russian
  `aria-label` describing the whole circuit in words — it doubles as the spec and
  as the accessible description. Width is fluid (`width:100%`), `min-width` keeps it
  legible.
- Background dot grid via the `<pattern id="dots3">` (already in the template's
  first figure — reuse the same id across figures in one file).
- Strokes that must follow the theme use `stroke="currentColor"`; power/GND nets
  use `stroke="var(--power)"`; accents `var(--ir)`. Fills likewise from vars.
- Component symbols are hand-built from `<line>`/`<path>`/`<circle>` — capacitor =
  two short parallel plates, ground = shrinking horizontal bars, no-connect hop =
  a small `A` arc on the crossing wire. Keep pin taps on real net coordinates so
  the drawing stays electrically honest, not just decorative.
- Reuse the section classes the template ships: `.notes`/`.note` (callout grid),
  BOM `table` with `td.ref`/`td.val`/`td.role`, `ol.steps` (ordered build/bring-up),
  `.aside` (side note). Match the existing docs rather than inventing new CSS.

## Numbers — compute, then double-check

Every value in a doc must be one you verified, not one you guessed. When a value
depends on a calculation (RC corner, divider voltage, gate drive, LED branch
current, common-mode headroom, LDO dropout/heat, pack voltage window), run the
arithmetic (Python) and put the checked figure in the BOM, the SVG label, and the
aria-label — all three, kept in sync. A stale figure in one place contradicting the
others is the most common defect here; grep the file for the old number after any
change. If two docs share a value (e.g. the same CC1101 pin), change both.

## Render verification — mandatory, both themes

You cannot see the page by reasoning about it; render it. The browser extension is
not available here, so drive headless Chrome and read the pixels. **The Cyrillic
username breaks tool paths — always stage and output under `C:/bb/` (ASCII).**

Use `scripts/render-check.sh <path-to-html>`; it writes `C:/bb/<name>_light.png`
and `C:/bb/<name>_dark.png`. Then crop the region you changed with PIL and Read the
crop. Key gotcha learned the hard way: **the `preferredColorScheme=2` Chrome flag
does NOT reliably trigger the dark media query** — the script forces dark by
injecting `data-theme="dark"` on `<html>` before render, which the page's
`:root[data-theme="dark"]` block honors. Light is forced with
`--blink-settings=preferredColorScheme=1`.

Look for: mojibake (charset), wires crossing labels or boxes, text overrunning its
box, a net that visually floats, a value that disagrees between SVG and caption,
and that both palettes are legible (teal/coral on dark, on light).

## Publish, commit, deploy

1. **Artifact** (theme-aware preview the user shares from a phone): publish the file
   with the Artifact tool. Give a stable emoji `favicon`, a short noun-phrase title
   (the `<title>` tag wins), and a one-line `description`. On updates, pass the
   existing artifact `url` so the link is preserved; keep the favicon stable.
2. **Git**: commit into `esp32-flipper-exp`. Conventional-commit subject
   (`docs(<doc>): …`), a body explaining the *why*, and the session trailers
   (`Co-Authored-By` + `Claude-Session`). Commit related docs together.
3. **GitHub Pages**: the site deploys from `main` / repo **root**. Keep a root
   `index.html` that links every doc in `docs/` (see `assets/index-template.html`).
   When adding a new doc, add its card to the root index in the same commit.
4. When a deliverable is meant to be shared, send it with SendUserFile so the user
   can forward it from mobile.

## Reference

- `assets/template.html` — the theme-aware skeleton + full CSS. Start here.
- `assets/index-template.html` — root Pages landing page linking the docs.
- `scripts/render-check.sh` — headless render of both themes to `C:/bb/`.
