# citefix

> Paste a passage and its reference list. For every citation, citefix checks that the paper exists, that it actually supports the sentence citing it, and, if it does not, finds a real paper that does.

Built for the [Silicon Valley Buildathon](https://silicon-valley-buildathon.devpost.com/) 2026. 中文说明见 [README.zh-CN.md](README.zh-CN.md)。

**Live demo:** https://citefix-g7nq.onrender.com. It runs on a free Render instance, which sleeps after 15 idle minutes, so the first visit may take about a minute to wake it.

## Why

Language models write convincing references that do not exist, and real references get attached to sentences they never support. Checking every citation by hand means opening every paper. citefix does the lookup and the reading, and shows its evidence so you can check each verdict yourself.

## How it works

1. **Does the paper exist?** Each reference is parsed (APA, IEEE, ACM or GB/T 7714) and looked up in OpenAlex, Crossref and arXiv. Existence is decided only from those records, never from a language model's memory.
2. **Does it support the sentence?** A model (DeepSeek) finds each citation in the passage, then compares the claim with the cited paper's abstract. To call a citation supported, it has to quote the abstract sentence it relied on, and the quote is checked against the abstract.
3. **If not, which paper does?** An agent with two tools, `search_papers` and `submit`, looks for a paper that supports the claim. Its suggestion is accepted only if the paper came from its own searches, its quote appears in that paper's abstract, and a separate judging call agrees. When the claim itself is wrong, it suggests rewriting the sentence instead of forcing a citation.

The web page writes the results on the passage like proof marks: a green underline for supported, a dotted amber line for partly supported or unclear, a red wave for not supported or not found, and a blue-pencil insertion for the agent's replacement. Each verdict sits in the margin next to its sentence, with the quote it rests on.

## Run it

Python 3.10 or later, standard library only.

```bash
python -m citefix serve                         # web app at http://localhost:8765
python -m citefix review examples/passage.txt   # the same check on the command line
python -m citefix check examples/refs.txt --trace
```

Put keys in `.env` (copy `.env.example`):

| Variable | |
|---|---|
| `DEEPSEEK_API_KEY` | Required for steps 2 and 3. |
| `OPENALEX_API_KEY` | Strongly recommended. Without a key, OpenAlex shares one small daily budget among everyone on your IP address. Keys are free: https://help.openalex.org/api/authentication/ |
| `S2_API_KEY` | Optional; Semantic Scholar is skipped without it. |
| `CROSSREF_MAILTO` | Optional contact address for Crossref's polite pool. |

For a public deployment (see `render.yaml` and `Dockerfile`), `CITEFIX_PER_IP_PER_HOUR` (40 in the Dockerfile, since a class on one campus network shares an address) and `CITEFIX_DAILY_LIMIT` (200) cap how many checks visitors can run. At most two checks run at once; a third waits in line and starts when one finishes.

## Tester feedback

After a check, each note asks "Is this right?", and a panel under the notes takes a 1 to 5 rating and a comment. Nothing is sent until the tester presses Send. Each send is printed to the server log as a `FEEDBACK {...}` line, saved as a JSON file under `FEEDBACK_DIR` (default `feedback/`), and, when `FEEDBACK_REPO` (`owner/name`) and `FEEDBACK_GITHUB_TOKEN` (a fine-grained token that can write only that repository's contents) are set, committed to that private repository. That last copy matters on a free instance, which loses its disk when it sleeps.

```bash
python eval/feedback_report.py path/to/citefix-feedback   # or a saved server log
```

The report is Markdown: how often each kind of verdict was marked right, per deployed version, every note marked wrong with the tester's reason, and every comment. The plan for testing with classmates is in [docs/user-testing.zh-CN.md](docs/user-testing.zh-CN.md).

## How it was tested

These are small hand-written test sets built on well-known papers, so the numbers are a sanity check, not a benchmark; the language model may already know these papers.

| Step | Test set | Result |
|---|---|---|
| 1. Does it exist? | 16 real references in four styles, 2 real ones with a wrong year or first author, 10 made up | All 10 made-up references caught; 15 of 16 real ones verified; no real reference called "not found"; both wrong details flagged |
| 2. Does it support the sentence? | 14 claim and reference pairs: 6 supported, 6 not, 2 partly | All 14 judged correctly; all 13 quotes found in the abstracts |
| 3. Does it find a real source? | 5 claims citing the wrong paper, 2 false claims | 7 of 7: the original paper found for all 5 (ViT, BatchNorm, LoRA, DDPM, CLIP); a rewrite suggested for both false claims |

What testing changed:

- GAN (2014) was first marked suspicious because a better-cited 2020 paper with almost the same title ranked first. The checker now searches again within the cited year.
- OpenAlex writes GPT-3's first author as "Brown, Tom B.", which broke author matching. Matching now ignores name order.
- Crossref's response headers say its public pool allows one request per second. Requests now follow the pace a source announces.
- arXiv timed out during a live run and left the agent with no results. Timeouts no longer retry, Crossref was added as a search source, and failed sources are shown in the agent's trail.
- Known gap: Chinese-language works are poorly covered by these indexes.

Test sets and every run are in `eval/`; the round-by-round notes are in [README.zh-CN.md](README.zh-CN.md).

## Credits

Records from [OpenAlex](https://openalex.org), [Crossref](https://www.crossref.org), [arXiv](https://arxiv.org) and [Semantic Scholar](https://www.semanticscholar.org); judgments by [DeepSeek](https://www.deepseek.com) (`deepseek-flash`); the Literata typeface via Google Fonts.
