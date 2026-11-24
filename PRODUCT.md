# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Plain HTML, CSS and JavaScript with no build step, served by the project's own Python standard-library server (`python -m citefix serve`). Chosen by the user.

## Users

Students writing theses and papers who want to know, before they submit, whether every citation in a passage is real and actually says what they cite it for. Judges of the Silicon Valley Buildathon evaluate the product from a 2–3 minute demo video and may try the live page.

## Product Purpose

The student pastes a passage and its reference list. citefix checks every citation in three steps: does the cited paper exist, does its abstract support the sentence that cites it, and if not, which real paper does. Success means the student fixes the problem citations using evidence they can verify themselves.

## Positioning

Checking that references exist is already common (CheckIfExist, check-hallucinations, CiteAudit and others). citefix checks claim-level support against the abstract and repairs failing citations with an agent, and it takes nothing on the model's word: existence comes only from scholarly indexes, every quote must appear in the abstract it is attributed to, and the agent may only suggest papers its own searches returned, each confirmed by an independent check.

## Operating Context

Used on a laptop while revising a manuscript. Input is pasted text: the body, a line that says References, then one reference per line (APA, IEEE, ACM or GB/T 7714). Records come from OpenAlex, Crossref, arXiv and Semantic Scholar, with abstracts also from PubMed; judgments come from DeepSeek (`deepseek-flash`). The demo is recorded for the Buildathon, whose deadline is 2026-12-15 23:45 EST.

## Capabilities and Constraints

- Interface language: English.
- Progress streams live from the server; checking the four-citation example takes about 25 seconds.
- Free-tier limits: Crossref allows one request per second; OpenAlex needs a free key; Semantic Scholar is only used with a key.
- Chinese-language references are poorly covered by the available indexes (known gap).
- Deployment: Render's free web service (Docker), with the code in a public GitHub repository. Free instances sleep after 15 idle minutes and take about a minute to wake. The public demo caps checks per visitor and per day. (Hugging Face's free tier only allows static Spaces, which cannot run the Python backend.)
- Undecided: the product name (citefix is a working name).

## Evidence on Hand

- Evaluation results in `eval/results/` and `README.md`: step 1 on 28 references, step 2 on 14 claim/reference pairs, step 3 on 7 claims. These are small hand-written sets built on well-known papers and must be described that way.
- Six literature-review paragraphs written by DeepSeek, whose 30 references and 30 citations Claude (an AI) labelled against the indexes and abstracts (`eval/data/llm_passages.json`). No person has reviewed the labels yet, and they must be described that way.
- Example passage: `examples/passage.txt`.
- There are no user testimonials or usage numbers yet; none may be invented.

## Product Principles

1. Show the evidence, not just the verdict: every judgment comes with the source sentence it rests on.
2. The model never vouches: existence comes from databases, quotes are verified, suggestions are re-checked.
3. Prefer "can't tell" over a false accusation.
4. Fixing beats flagging: when a citation fails, offer the real paper or a corrected claim.
