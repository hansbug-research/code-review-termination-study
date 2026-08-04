#!/usr/bin/env python3
"""从已下载的文献全文中抽取摘要与全部含数值的句子，供逐条核对引文。

不做任何改写或概括——只做定位。输出的每一行都是原文句子，便于把报告里的每个数字回溯到
它在原文中的确切措辞。

用法：
    python3 scripts/lit_digest.py 2604.22273              # 摘要 + 数值句
    python3 scripts/lit_digest.py 2604.22273 --grep EIR   # 只看含关键词的句子
    python3 scripts/lit_digest.py 2604.22273 --section results   # 打印某节全文
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

WORK = Path(os.environ.get("LIT_WORKDIR", "/tmp/lit"))


def strip_tex(text: str) -> str:
    text = re.sub(r"(?m)^\s*%.*$", "", text)          # 整行注释
    text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.M)  # 行内注释
    text = re.sub(r"\\(cite[a-z]*|ref|label|autoref|Cref|cref)\{[^}]*\}", "", text)
    text = re.sub(r"\\(textbf|textit|emph|texttt|textsc|mbox)\{([^{}]*)\}", r"\2", text)
    text = re.sub(r"\\(begin|end)\{(figure|table|tabular|algorithm)\*?\}", "\n", text)
    text = re.sub(r"~", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text


def sentences(text: str) -> list[str]:
    text = re.sub(r"\n{2,}", " \x00 ", text)
    text = text.replace("\n", " ")
    out = []
    for para in text.split("\x00"):
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(\\$])", para):
            s = s.strip()
            if 25 <= len(s) <= 900:
                out.append(s)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--grep", default=None)
    ap.add_argument("--section", default=None)
    ap.add_argument("--max", type=int, default=200)
    args = ap.parse_args()

    path = WORK / f"{args.key}.txt"
    raw = path.read_text(errors="replace")
    body = strip_tex(raw)

    if args.section:
        pat = re.compile(r"\\(sub)*section\*?\{[^}]*" + re.escape(args.section) + r"[^}]*\}", re.I)
        m = pat.search(body)
        if not m:
            pat2 = re.compile(r"(?mi)^\s*\d*\.?\s*" + re.escape(args.section) + r"\s*$")
            m = pat2.search(body)
        if not m:
            print(f"未找到章节 {args.section!r}")
            return
        nxt = re.search(r"\\(sub)*section\*?\{", body[m.end():])
        end = m.end() + (nxt.start() if nxt else 12000)
        print(body[m.start():end][:14000])
        return

    if args.grep:
        keys = [k.strip().lower() for k in args.grep.split("|")]
        hits = [s for s in sentences(body) if any(k in s.lower() for k in keys)]
    else:
        m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, re.S)
        if m:
            print("=== ABSTRACT ===")
            print(" ".join(m.group(1).split())[:2600])
            print()
        hits = [s for s in sentences(body)
                if re.search(r"\d+\.\d+\s*%|\d+\s*%|\bp\s*[<=]\s*0?\.\d|\b\d{2,3}[,.]\d{3}\b", s)]
    print(f"=== {'GREP' if args.grep else 'NUMERIC'} SENTENCES ({min(len(hits), args.max)}/{len(hits)}) ===")
    seen = set()
    n = 0
    for s in hits:
        k = s[:80]
        if k in seen:
            continue
        seen.add(k)
        print(f"- {' '.join(s.split())}")
        n += 1
        if n >= args.max:
            break


if __name__ == "__main__":
    main()
