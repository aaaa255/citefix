# citefix

> Paste a passage and its reference list. For every citation, citefix checks that the paper exists, that it actually supports the sentence citing it, and, if it does not, finds a real paper that does.

Built for the [Silicon Valley Buildathon](https://silicon-valley-buildathon.devpost.com/) 2026. 中文说明见 [README.zh-CN.md](README.zh-CN.md)。

**Live demo:** https://citefix-g7nq.onrender.com. It runs on a free Render instance, which sleeps after 15 idle minutes, so the first visit may take about a minute to wake it.

## Why

Language models write convincing references that do not exist, and real references get attached to sentences they never support. Checking every citation by hand means opening every paper. citefix does the lookup and the reading, and shows its evidence so you can check each verdict yourself.

## How it works

1. **Does the paper exist?** A reference that a PDF or word processor wrapped onto several lines is first joined back up. Each reference is parsed (APA, IEEE, ACM or GB/T 7714) and looked up in OpenAlex, Crossref and arXiv, and by its DOI when it has one. Where a preprint and its published version share a title, citefix shows the version the reference cites: the one with its DOI, else the one from its year, else the published one unless it names a preprint server. Existence is decided only from those records, never from a language model's memory.
2. **Does it support the sentence?** A model (DeepSeek) finds each citation in the passage, then compares the claim with the cited paper's abstract, taken from the records step 1 found, else from [PubMed](https://pubmed.ncbi.nlm.nih.gov) by DOI, else from arXiv by title. To call a citation supported, it has to quote the abstract sentence it relied on, and the quote is checked against the abstract.
3. **If not, which paper does?** An agent with two tools, `search_papers` and `submit`, looks for a paper that supports the claim. Its suggestion is accepted only if the paper came from its own searches, its quote appears in that paper's abstract, and a separate judging call agrees. When the claim itself is wrong, it suggests rewriting the sentence instead of forcing a citation. A rewrite passes the same checks: it names the paper whose abstract supports it, either the one already cited, which keeps its number, or one from the agent's searches, which the page then offers to cite instead.

The web page writes the results on the passage like proof marks: a green underline for supported, a dotted orange line for partly supported or unclear, a red wave for not supported or not found, and an insertion highlighted in yellow for the agent's replacement. Each verdict sits in the margin next to its sentence, with the quote it rests on.

## Run it

Python 3.10 or later, standard library only.

```bash
python -m citefix serve                         # web app at http://localhost:8765
python -m citefix review examples/passage.txt   # the same check on the command line
python -m citefix check examples/refs.txt --trace
```

The web page is a React app in `frontend/` (Vite, Tailwind CSS, Motion, Lucide). The server serves its build from `frontend/dist`; build it once with Node 20.19 or later:

```bash
cd frontend && npm install && npm run build
```

Without a build, the server falls back to the earlier plain-HTML page in `citefix/web/`. The Dockerfile builds the page itself, so Render needs nothing extra. For work on the page, `npm run dev` in `frontend/` serves it at http://localhost:5173 and forwards `/api` to the Python server on port 8765 (see [frontend/README.md](frontend/README.md)).

Put keys in `.env` (copy `.env.example`):

| Variable | |
|---|---|
| `DEEPSEEK_API_KEY` | Required for steps 2 and 3. |
| `OPENALEX_API_KEY` | Strongly recommended. Without a key, OpenAlex shares one small daily budget among everyone on your IP address. Keys are free: https://help.openalex.org/api/authentication/ |
| `S2_API_KEY` | Optional; Semantic Scholar is skipped without it. |
| `CROSSREF_MAILTO` | Optional contact address for Crossref's polite pool. |

Lookups are kept in memory for six hours (`CITEFIX_CACHE_HOURS`; 0 turns this off), so checking the same references again skips the indexes: step 1 on the four example references took 7.7 s the first time and 0.02 s the second.

For a public deployment (see `render.yaml` and `Dockerfile`), `CITEFIX_PER_IP_PER_HOUR` (40 in the Dockerfile, since a class on one campus network shares an address) and `CITEFIX_DAILY_LIMIT` (200) cap how many checks visitors can run. At most two checks run at once; a third waits in line and starts when one finishes.

## Tester feedback

After a check, each note asks "Is this right?", and a panel under the notes takes a 1 to 5 rating and a comment. Nothing is sent until the tester presses Send. Each send is printed to the server log as a `FEEDBACK {...}` line, saved as a JSON file under `FEEDBACK_DIR` (default `feedback/`), and, when `FEEDBACK_REPO` (`owner/name`) and `FEEDBACK_GITHUB_TOKEN` (a fine-grained token that can write only that repository's contents) are set, committed to that private repository. That last copy matters on a free instance, which loses its disk when it sleeps.

```bash
python eval/feedback_report.py path/to/citefix-feedback   # or a saved server log
```

The report is Markdown: how often each kind of verdict was marked right, per deployed version, every note marked wrong with the tester's reason, and every comment. It counts people only: replays, sends signed "test" and testers whose name contains "(AI)" are left out; `--ai` reports the AI testers, and `--all` counts everything. The plan for testing with classmates is in [docs/user-testing.zh-CN.md](docs/user-testing.zh-CN.md).

## How it was tested

These are small hand-written test sets built on well-known papers, so the numbers are a sanity check, not a benchmark; the language model may already know these papers.

| Step | Test set | Result |
|---|---|---|
| 1. Does it exist? | 16 real references in four styles, 2 real ones with a wrong year or first author, 10 made up | All 10 made-up references caught; 15 of 16 real ones verified; no real reference called "not found"; both wrong details flagged |
| 2. Does it support the sentence? | 14 claim and reference pairs: 6 supported, 6 not, 2 partly | All 14 judged correctly; all 13 quotes found in the abstracts |
| 3. Does it find a real source? | 5 claims citing the wrong paper, 2 false claims | 7 of 7: the original paper found for all 5 (ViT, BatchNorm, LoRA, DDPM, CLIP); a rewrite suggested for both false claims |

**Harder data.** DeepSeek (`deepseek-v4-pro`) wrote six literature-review paragraphs in six fields, each with five numbered citations, the way a student might ask a chatbot for one. Before citefix ran, Claude (an AI) checked every reference in OpenAlex, Crossref and PubMed and judged every citation against the cited paper's abstract; no person has reviewed these labels yet. 29 of the 30 references were real. The abstracts clearly supported only 4 of the 29 citations of real papers, though; for 15, the abstract does not support the sentence or supports only part of it. citefix read five of the six passages. It called the made-up reference not found, verified 23 of the 24 real references it read, flagged all 8 clearly unsupported citations it could judge, and passed 3 of the 4 clearly supported ones. That first run found four problems, all fixed since (see "What testing changed" below):

- Eight of the eleven suggested rewrites kept the original citation number. Seven reworded the sentence from another paper the agent found, which the page did not show, and one kept the number of the made-up reference.
- A "References" heading placed at the end of the last sentence, not on its own line, was missed, so the sixth passage could not be checked.
- A title with a question mark before its subtitle was cut short, so a real reference with the right DOI was called suspicious.
- Five citations could not be judged because OpenAlex and Crossref have no abstract for those papers. PubMed has all five.

The passages and labels are in `eval/data/llm_passages.json`; `python eval/run_llm_passages.py` runs them.

**False alarms on published papers.** To see how citefix treats citations that are mostly right, five introduction paragraphs were taken from open-access papers (CC BY or CC0, from PubMed Central) in psychology, environmental science, economics, medicine and NLP: 29 references and 31 citations written by the papers' own authors (`eval/data/oa_passages.json`, built by `eval/make_oa_passages.py`; labelled by Claude, an AI, before citefix ran, and not yet reviewed by a person). Step 1 verified all 26 real references and flagged the one the original paper got wrong (2014 for 2004); a report and a web page that the indexes do not hold were not verified. Six citations had no abstract to judge. Of the 23 that did, all 4 clearly supported ones passed and all 9 that should be flagged were, but 18 of the 23 were flagged in all. That is mostly not a wrong verdict: authors cite papers as examples ("studies have primarily focused on the Great Lakes region [1–5]", where each abstract only shows a Great Lakes study) or for details beyond the abstract. Three of those flags were harsher than the abstracts justify: "not supported" for papers on the right subject whose abstracts simply leave out the comparison the sentence makes. Two rewordings of the judge's instructions were tried on all 66 labelled citations, six runs each. Keeping "not supported" for contradictions and other subjects, and sending on-topic silence to "insufficient evidence", halved such red marks (6 of 252 judgments, against 13) but flagged clearly supported citations more often (7 of 84, against 2); narrowing "not supported" alone cut neither. The instructions stay as they were.

**Repeated judging.** A model's verdicts vary from run to run, so each of 43 labelled citations (the 29 citations of real papers above and the 14 hand-written pairs) was judged three times by the current judge, `deepseek-flash`, and three times by `deepseek-v4-pro` (`python eval/run_judge_repeats.py`; run by Claude, an AI). flash flagged 1 of 30 judgments it should have passed and let through none of 69 it should have flagged; v4-pro flagged none and let one through. They differ on borderline citations, which flash flagged 26 times in 30 and v4-pro 18 times. flash gave the same verdict in all three runs for 38 of the 43 citations and v4-pro for 35, and v4-pro took twice as long, so the default stays. Keeping the majority of three verdicts removed every error for both models on these 43 citations, at three times the judging calls; that trade is not settled. In the full check, clearly supported citations were flagged more often (2 of 12 judgments), and the check judges the claim the extraction step wrote, which drops author names ("Roediger and Karpicke demonstrated that..."). Judging the four clearly supported citations eight times in each form, the sentence was called supported 28 times in 32 and the extracted claim 25; the whole gap came from one citation (7 against 4 of 8), too little to change anything yet.

What testing changed:

- GAN (2014) was first marked suspicious because a better-cited 2020 paper with almost the same title ranked first. The checker now searches again within the cited year.
- OpenAlex writes GPT-3's first author as "Brown, Tom B.", which broke author matching. Matching now ignores name order.
- Crossref's response headers say its public pool allows one request per second. Requests now follow the pace a source announces.
- arXiv timed out during a live run and left the agent with no results. Timeouts no longer retry, Crossref was added as a search source, and failed sources are shown in the agent's trail.
- Without a key, everyone on the same IP address shares one small OpenAlex budget. It ran out partway through one test run, and again on the deployed server. Both now use a free key: two reruns gave the same numbers, with no failed lookups.
- In a simulated user test, an AI agent (Codex) played the user on the live site and marked one note wrong. The cited paper's abstract could not settle the claim, yet citefix said "Cite instead" for a paper that only partly supported it. "Cite instead" now needs a citation that was not found or does not support the sentence, and a replacement the second check says fully supports it. Any other find is shown as a "Possible source", with the reason.
- The same run found four smaller problems, now fixed. Check citations could be pressed before Load example had filled the editor. The status line named only one of two running searches. Two verdicts in one sentence shared one underline. Reasons for a wrong mark were cut off at 300 characters. Now the example loads with the page, the status line names every search, each citation number takes its own verdict's ink, and reasons can run to 1,000 characters.
- In the first test with a person, a classmate ran five checks on the live site, one per case: a directly supported claim, a real paper cited for something it never says, a made-up reference, accurate numbers worded as cause and effect, and one reference number behind two opposite sentences. All six notes were marked right, with an average rating of 4.2 out of 5, and the five problems found were in the details. A reference that gave BERT's NAACL 2019 DOI was shown as the 2018 arXiv preprint. References are now also looked up by DOI, and a DOI that leads to a different paper makes a reference suspicious.
- Suggested references wrote Edward J. Hu as "Hu, J. E.", lacked volume and pages, and linked to OpenAlex. They now keep the names as printed, add volume, issue and pages, and link to the publisher. A rewritten sentence lost its "[1]"; rewrites now keep their numbers. Two notes headed [1] could not be told apart, since on a wide screen the second is pushed down, away from its sentence; a number cited in more than one sentence now shows the start of each sentence in its notes.
- Rerunning step 1 showed the same version problem without a DOI: the version picked depended on the order OpenAlex returned, which changed between runs. BERT, RAG and ResNet, all cited from conference proceedings, were each matched to an arXiv preprint in some run. citefix now prefers the version from the cited year, then the published one unless the reference names a preprint server. All 28 verdicts stayed the same.
- In the passages a language model wrote, a suggested rewrite kept the sentence's citation number even when the agent had reworded it from another paper, or when the cited reference was made up. A rewrite now names the paper whose abstract supports it and passes the same independent check as a suggested paper. It keeps the number only when the cited paper itself supports it; otherwise the page offers the new paper to cite instead. On a rerun all 13 rewrites passed that check: 3 kept their number and 10 cite the paper behind them, including the one for the made-up reference. The hand-written step 3 set scored 6 of 7 in two reruns. The miss is DDPM: OpenAlex now holds an unrelated GitHub README as its abstract, so the agent passed it over, and the code before this change misses it too.
- The same passages showed three ways a check could not even start. A "References" heading at the end of the last sentence now counts when a reference list follows it. A title cut short at a question mark now matches a record whose full title starts with it and appears whole in the reference. And when OpenAlex and Crossref have no abstract, citefix asks PubMed by DOI. On a rerun all six passages were read, all 29 real references verified and all 29 citations of real papers judged: all 15 clearly unsupported ones were flagged and all 4 clearly supported ones passed. The model's verdicts vary between runs, though; in the two runs before, two or three of the same citations got a different verdict. The step 1 set gave the same numbers as before.
- Indexes sometimes keep something other than an abstract in the abstract field: OpenAlex holds an unrelated GitHub README for DDPM and the acknowledgments for Brown et al. (1982). citefix now skips text that reads like a README or acknowledgments, publication details, anything under 20 words, and text sharing no word with the title, and looks for the abstract in another record of the paper, in PubMed or in arXiv. The step 3 set is back to 7 of 7, with DDPM's real abstract from arXiv, and Brown et al. is judged against the survey's own abstract from its working-paper version. On the passages, all 15 clearly unsupported citations were flagged again, but only 2 of the 4 clearly supported ones passed this time, against 3, 3 and 4 in earlier runs; their abstracts were the same as before, so this is the judge's variation, not the change.
- The agent often suggested a paper's arXiv preprint even when it was published, since arXiv results always carry an abstract. Its search results now merge a preprint and its published version (same title, same first author) into one record with the published details and the abstract the agent saw. On the step 3 set, suggested papers that were preprints went from 4 of 7 to 2 of 7: ViT now names ICLR and DDPM NeurIPS, LoRA's ICLR version was not among the results, and Hinton et al. (2012) exists only on arXiv. Both runs got 7 of 7 right.
- Timing the agent showed every search waiting on arXiv, which asks for 3 s between calls: on the step 3 set its 11 calls added up to 48.5 s. A search now asks OpenAlex first (it covers arXiv), Crossref only when OpenAlex returns fewer than three papers with an abstract, and arXiv only for up to two leading preprint or proceedings records that lack one. The agents' part of the step 3 set went from 36 s to 22 s with 2 arXiv calls instead of 11, still 7 of 7 right in two runs; a full check of the example passage went from 14–19 s to 12–14 s with the same verdicts.
- Known gap: Chinese-language works are poorly covered by these indexes.

Test sets and each round's results are in `eval/`; the round-by-round notes are in [README.zh-CN.md](README.zh-CN.md). The evaluation scripts keep the indexes' replies in `eval/.cache/` for a week, so a rerun does not spend the OpenAlex budget again (repeated runs on 2026-11-25 used up a day's budget); set `CITEFIX_EVAL_CACHE=0` for a fresh run, for example to time one.

## Credits

Records from [OpenAlex](https://openalex.org), [Crossref](https://www.crossref.org), [arXiv](https://arxiv.org) and [Semantic Scholar](https://www.semanticscholar.org); judgments by [DeepSeek](https://www.deepseek.com) (`deepseek-flash`). The page is built with [React](https://react.dev), [Vite](https://vite.dev), [Tailwind CSS](https://tailwindcss.com), [Motion](https://motion.dev) and [Lucide](https://lucide.dev) icons, and set in the Geist and Literata typefaces, self-hosted from [Fontsource](https://fontsource.org) (the classic page loads Literata from Google Fonts).
