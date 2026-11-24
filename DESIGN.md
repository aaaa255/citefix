---
name: citefix
description: Every citation, checked against its source, with the verdict written in the margin.
colors:
  ink-blue-shell: "#102542"
  shell-ink: "#eef2f9"
  shell-ink-soft: "#b7c4da"
  blue-pencil: "#1f4fd8"
  blue-pencil-light: "#9db8ff"
  stet-green: "#157a3c"
  query-amber: "#965905"
  proof-red: "#bd172b"
  sheet-white: "#ffffff"
  cool-desk: "#edf0f4"
  graphite: "#1b1f24"
  graphite-soft: "#454d57"
  slate-note: "#636d78"
  hairline: "#e1e5ea"
  hairline-strong: "#c6cdd6"
  pencil-wash: "#ebf0fd"
  stet-wash: "#e8f5ed"
  query-wash: "#fcf2e1"
  proof-wash: "#fcebed"
typography:
  wordmark:
    fontFamily: "Literata, 'Iowan Old Style', Charter, Georgia, serif"
    fontSize: "23px"
    fontWeight: 650
    lineHeight: 1
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Literata, 'Iowan Old Style', Charter, Georgia, serif"
    fontSize: "17.5px"
    fontWeight: 400
    lineHeight: 1.85
  quote:
    fontFamily: "Literata, 'Iowan Old Style', Charter, Georgia, serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.3
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.5
  data:
    fontFamily: "ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace"
    fontSize: "12.5px"
    fontWeight: 400
rounded:
  quote: "8px"
  button: "9px"
  note: "10px"
  sheet: "14px"
spacing:
  gutter: "clamp(16px, 3vw, 36px)"
  column: "clamp(20px, 4.5vw, 68px)"
  note-gap: "8px"
components:
  button-primary:
    backgroundColor: "{colors.shell-ink}"
    textColor: "{colors.ink-blue-shell}"
    rounded: "{rounded.button}"
    padding: "10px 17px"
    typography: "{typography.title}"
  button-primary-hover:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.ink-blue-shell}"
  button-ghost:
    backgroundColor: "{colors.ink-blue-shell}"
    textColor: "{colors.shell-ink}"
    rounded: "{rounded.button}"
    padding: "10px 17px"
  button-small:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.blue-pencil}"
    rounded: "{rounded.quote}"
    padding: "7px 11px"
  evidence-supported:
    backgroundColor: "{colors.stet-wash}"
    textColor: "{colors.graphite}"
    rounded: "{rounded.quote}"
    padding: "7px 11px"
    typography: "{typography.quote}"
  evidence-suggested:
    backgroundColor: "{colors.pencil-wash}"
    textColor: "{colors.graphite}"
    rounded: "{rounded.quote}"
    padding: "7px 11px"
    typography: "{typography.quote}"
  margin-note:
    textColor: "{colors.graphite-soft}"
    rounded: "{rounded.note}"
    padding: "8px 10px 10px"
    typography: "{typography.label}"
---

# Design System: citefix

## Overview

**Creative North Star: "The Proof Room"**

citefix treats the student's manuscript as a galley proof on an editor's desk. The text is the interface: each citation is checked in place, and its verdict is written in the margin beside the sentence, the way a copy-editor marks a proof. A cool grey desk holds one white sheet; a deep ink-blue bar carries the product's own controls. Everything else on the page is ink, and each ink has exactly one job.

The page is calm and dense in the way a well-set proof is dense: one reading column at about 68 characters, a ruled margin column of short notes, and a reference list under the text. Motion is reserved for the moment a verdict lands: the underline inks in, the note slides into the margin, and an inserted citation drops into the line in blue pencil.

**Key Characteristics:**
- The manuscript, not a card list, carries the results.
- Four inks with fixed meanings: stet green, query amber, proof red, blue pencil.
- Literata for everything a person reads at length; the system sans for controls; mono only for DOIs and ids.
- Evidence is always shown: a verdict without its quoted sentence is incomplete.
- One sheet, one shadow, no ornament.

## Colors

A restrained proof-room palette: cool neutrals, one committed ink-blue shell, and four working inks that only ever mean one thing.

### Primary
- **Ink-Blue Shell** (`ink-blue-shell`): the top bar, the favicon and the text of the primary button. It is the product's own voice, kept out of the manuscript.
- **Blue Pencil** (`blue-pencil`): the agent's work and the app's actions inside the sheet: inserted citations, the "Cite instead" block, the agent trail, links, focus rings, the progress line.

### Secondary
- **Stet Green** (`stet-green`): supported citations and found references. Solid underline in the text, check icon and verdict in the margin, its wash behind supporting quotes.
- **Query Amber** (`query-amber`): partly supported, can't tell, details differ. Dotted underline, warning icon.
- **Proof Red** (`proof-red`): not supported, reference not found, struck citation numbers. Wavy underline, cross icon.

### Neutral
- **Sheet White** (`sheet-white`): the manuscript sheet.
- **Cool Desk** (`cool-desk`): the page ground around the sheet; deliberately cool, never cream.
- **Graphite** (`graphite`), **Graphite Soft** (`graphite-soft`), **Slate Note** (`slate-note`): text in three steps: manuscript and quotes, notes and explanations, metadata and hints.
- **Hairline** (`hairline`), **Hairline Strong** (`hairline-strong`): the margin rule, dividers, pending underlines, small-button borders.
- **Washes** (`stet-wash`, `query-wash`, `proof-wash`, `pencil-wash`): quote backgrounds and hover highlights, always paired with their ink.

### Named Rules
**The One Ink, One Job Rule.** Green only ever means supported, amber only ever means uncertain, red only ever means wrong or missing, blue only ever means the agent's suggestion or an action. No ink is used for decoration.

**The Shell Stays Out of the Text Rule.** Ink-blue belongs to the bar and controls. The manuscript is graphite on white until a verdict marks it.

Dark mode keeps the same roles with lighter inks on a near-black sheet; the values live in `citefix/web/style.css` under `prefers-color-scheme: dark`.

## Typography

**Display Font:** Literata (with Iowan Old Style, Charter, Georgia)
**Body Font:** Literata for reading; the system UI sans for controls and notes
**Label/Mono Font:** the system monospace, for DOIs and arXiv ids only

**Character:** A screen-tuned book face for the student's own words and for every quote from a source, so evidence reads like text, not like interface. The system sans keeps every control instantly familiar.

### Hierarchy
- **Wordmark** (650, 23px, line-height 1): the product name in the bar, with the blue-pencil caret.
- **Body** (400, 17.5px, line-height 1.85, max 68ch): the manuscript proof. 17px in the editor, 16.5px on phones.
- **Quote** (italic 400, 14px, line-height 1.5): sentences quoted from abstracts.
- **Title** (600, 14px): column headings (Manuscript, Checks, References) and buttons, in Slate Note.
- **Label** (400, 13.5px, line-height 1.5): margin notes, status, reference details.
- **Data** (mono, 12.5px): DOIs and ids.

### Named Rules
**The Evidence Reads Like Text Rule.** Anything quoted from a source is set in Literata italic on its ink's wash, never in the UI sans.

## Layout

One sheet, centred, at most 1320px wide, on the desk with a `clamp(16px, 3vw, 36px)` gutter. Inside it a two-column grid: the manuscript column (flexible) with the reference list below it, and a margin column of 300–390px separated by a one-pixel rule. Notes are positioned beside the sentence they belong to and pushed down only as far as needed to avoid overlap (8px apart).

Under 960px the sheet becomes one column in reading order: manuscript, checks, references, with notes in normal flow. Under 560px the bar's two buttons share the full width and the purpose line is hidden. Nothing scrolls sideways at 375px.

## Elevation & Depth

Flat except for the sheet itself. The sheet is the only lifted object: it sits on the desk like paper.

### Shadow Vocabulary
- **Sheet** (`box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06), 0 22px 44px -26px rgba(15, 23, 42, 0.3)`): the manuscript sheet only.

### Named Rules
**The One Sheet Rule.** Nothing inside the sheet casts a shadow. Notes, quotes and buttons separate by space, washes and hairlines.

## Shapes

Softly squared paper geometry: the sheet at 14px, notes at 10px (visible only on hover), buttons at 9px, quotes and small buttons at 8px. Rules are one pixel; the only dashed line is the divider above a suggested fix. No pills, no circles except the small pending pulse.

## Components

### Buttons
- **Shape:** gently squared (9px; small buttons 8px).
- **Primary:** Shell Ink fill with Ink-Blue Shell text, 10px × 17px, on the bar. Hover turns it pure white. While a check runs it becomes **Stop**: transparent with a Shell Ink Soft outline.
- **Ghost:** transparent on the bar with a faint light outline (Load example).
- **Small:** white with a Hairline Strong border and Blue Pencil text and icon (Copy reference, Open paper); the border turns blue on hover.
- **Text:** Blue Pencil text only (Edit text).
- **Focus:** a 2px Blue Pencil ring with 2px offset on every control.

### Proof marks (signature component)
- **Pending:** dashed Hairline Strong underline.
- **Supported:** solid Stet Green underline, 2px, offset 0.32em.
- **Uncertain:** dotted Query Amber underline, 3px.
- **Wrong or missing:** wavy Proof Red underline, 1.5px.
- **Struck citation:** the old number in Slate Note with a 2px Proof Red line through it.
- **Insertion:** a Blue Pencil caret and the new citation in Literata italic, placed after the sentence, inking in from above. Only a "Cite instead" fix gets one.
- **Citation numbers:** each number takes its own citation's ink (Stet Green, Query Amber or Proof Red), so a sentence with two citations shows both verdicts while its underline shows the worse one.
- Hovering a marked sentence highlights it and its notes with the pencil wash; clicking the sentence scrolls its first note into view, and clicking a number scrolls to that number's note and rings it in Blue Pencil for a moment.

### Margin notes
- **Head:** citation number in Slate Note, then the verdict with its icon in its ink.
- **Sentence line:** the start of the sentence the note checks, in Literata Graphite Soft on one line with an ellipsis. It appears where the number alone cannot tell notes apart: on narrow screens, where the notes stack below the text, and on any screen for a number cited in more than one sentence, since a later note for it may be pushed below its sentence.
- **Source line:** authors, year and title on one line, truncated with an ellipsis.
- **Body:** the supporting quote for supported citations; the reason (three lines, click to open) for the rest, with the abstract's sentence behind "What the abstract says".
- **Agent trail:** a disclosure that is open while the agent works and collapses to "Agent searched N times" when it finishes; failed sources are named in amber.
- **Fix:** below a dashed rule, a label in Blue Pencil, the reference in Literata, the quote on the pencil wash, the second-check line, and small buttons. The label is one of three:
  - "Cite instead" (caret) only when the citation was not found or does not support the sentence, and the second check says the new paper fully supports it.
  - "Possible source" (query mark) for any other paper the agent found. The second-check line says why it is only possible: the old citation may still be right, or the new abstract only partly supports the sentence.
  - "Rewrite the sentence". The rewrite keeps the sentence's citation numbers, put back before its final stop, both on screen and when copied.

### Tester feedback
- **Note mark:** under each finished note, "Is this right?" in Slate Note with two quiet toggles, Yes (check) and No (cross). A pressed toggle gets a Blue Pencil outline on the sheet colour: marking a note is the reader's action, so it never takes a verdict ink. No opens a two-line field for the reason, up to 1,000 characters, so a source link fits.
- **Panel:** after the notes, below a hairline: "How did citefix do?", how many notes were marked, a five-step rating (Hairline Strong boxes, the chosen one filled with Blue Pencil), a comment, an optional name, the privacy line in Slate Note, and **Send feedback**, the one filled Blue Pencil button inside the sheet. The finished-check status links down to it.

### Inputs / Fields
- **Editor:** borderless Literata on the sheet, Blue Pencil caret; focus shows a soft pencil-wash outline 12px out, so the sheet itself is the field.
- **Form fields** (feedback only): system sans 14px, Hairline Strong border, 8px radius; the border turns Blue Pencil on focus, with the usual ring.

### Navigation
- **Bar:** sticky Ink-Blue Shell bar with the wordmark, a one-line purpose in Shell Ink Soft, and the two buttons on the right.

## Do's and Don'ts

### Do:
- **Do** show the quoted sentence with every verdict, on the wash of its ink.
- **Do** keep the four inks to their single meanings, in the text and in the margin alike.
- **Do** keep notes short by default (verdict, source line, quote) and put explanations and agent trails behind one click.
- **Do** label any replayed or recorded check as such, in Blue Pencil, wherever its results appear.

### Don't:
- **Don't** turn results into a grid of same-size cards; the manuscript carries the results.
- **Don't** use ink colours for decoration, gradients or tinted backgrounds outside their washes.
- **Don't** add shadows inside the sheet or a coloured stripe down the side of a note.
- **Don't** set quotes or the manuscript in the UI sans, or use monospace for anything but identifiers.
