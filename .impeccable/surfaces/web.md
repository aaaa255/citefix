# Surface brief: citefix web app (`citefix/web/`)

Development-only. Never copy this file's contents into page source or anything the server sends.

Mode: Operate. Audience: students revising a manuscript; Buildathon judges watching the demo video.
Task: paste a passage and its references, run the check, read each citation's verdict and the evidence behind it, copy the fixes.

## Direction contract

THESIS: The manuscript is the interface. Each verdict is written in the margin beside its sentence, like a copy-editor's proof mark, instead of in a list of suggestion cards cut off from the text.

OWN-WORLD: A proof room. Cool grey desk, white sheet, deep ink-blue top bar. Each ink has one job: stet green means supported, query amber means partly supported or unclear, proof red means not supported or not found, blue pencil marks the agent's insertions. Literata for the manuscript and headings, the system sans for controls, mono only for DOIs and ids. Marks: a solid underline, a wavy underline, a struck citation number, a caret insertion carrying the replacement citation in blue.

STORY: The student pastes a passage and presses Check. Marks land sentence by sentence. The student reads why a citation fails from the quoted abstract, then copies the replacement the agent found and re-checked.

FIRST VIEWPORT: An ink-blue bar with the wordmark, a one-line purpose, Load example and Check citations. Below it, one sheet: the manuscript column (editable, then rendered as a proof) and a ruled margin column with a status line and notes aligned to their sentences. The references sit under the manuscript, each labelled found, details differ or not found.

FORM: Proof marks (校样批注), the first of four options presented to the user and chosen by them; no seed key, because the Impeccable launcher is not installed.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
