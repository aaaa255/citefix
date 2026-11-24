"""Ask a language model for literature-review paragraphs with references, the way a student might.

The passages go to eval/data/llm_passages.json with empty label lists. Each reference and each
citation is then labelled by hand against real records, before citefix is run on them
(eval/run_llm_passages.py).

    python eval/make_llm_passages.py [--model deepseek-v4-pro] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citefix import llm  # noqa: E402

TOPICS = [
    "how retrieval practice (the testing effect) improves long-term retention in university students",
    "social media use and depressive symptoms in adolescents",
    "microplastic pollution in freshwater ecosystems and its effects on fish",
    "the employment effects of minimum wage increases",
    "intermittent fasting compared with continuous calorie restriction for weight loss",
    "detecting hallucinations in the outputs of large language models",
]

PROMPT = ("I'm writing the literature review section of a paper on {topic}. Write one paragraph of about "
          "150 words that summarizes previous research, citing 5 papers with numbered citations like [1] and [2]. "
          "After the paragraph, write a line that says References, then the 5 references in APA 7th edition "
          "style, one per line, starting with [1], [2] and so on. Plain text only, no markdown.")


def tidy(text: str) -> str:
    """Drop markdown emphasis the model may add anyway, so that "**References**" still heads the list."""
    return re.sub(r"\*{1,2}([^*\n]+)\*{1,2}", r"\1", text).strip()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--out", default=str(ROOT / "eval" / "data" / "llm_passages.json"))
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():
        print(f"{out} already exists and holds hand-made labels, so it is not overwritten.", file=sys.stderr)
        return 1

    passages = []
    for number, topic in enumerate(TOPICS, 1):
        prompt = PROMPT.format(topic=topic)
        # Thinking off, like a chat app's default answer.
        message, _ = llm.chat([{"role": "user", "content": prompt}], model=args.model, effort="none",
                              max_tokens=2000)
        passages.append({"id": f"p{number:02d}", "topic": topic, "model": args.model,
                         "date": time.strftime("%Y-%m-%d"), "prompt": prompt,
                         "text": tidy(message.get("content") or ""), "references": [], "citations": []})
        print(f"--- {passages[-1]['id']}\n{passages[-1]['text']}\n")

    about = "Generated passages; label each reference and citation by hand before running citefix on them."
    out.write_text(json.dumps({"about": about, "passages": passages}, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(llm.usage_summary())
    print(f"saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
