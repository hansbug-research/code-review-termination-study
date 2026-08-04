#!/usr/bin/env python3
"""由 lit/references.json 生成参考文献表与 BibTeX，并回填进 report.md。

为什么要生成而不是手写。参考文献是正文可追溯性的最后一环：若著录信息是手打的，它既不能
被机器核对，也无法保证与 lit/manifest.csv 的校验和、与 lit/quotes.md 的引文对应。本脚本
把三者绑定成一条链——

    lit/references.json  （权威接口取回的著录信息 + 取回日期）
        → report.md 的参考文献表（编号 + 锚点 + DOI + SHA-256）
        → references.bib（供外部工具复用）
        → scripts/verify.py（核对正文引用编号与锚点一一对应、无孤儿、无未被引用项）

编号规则是确定性的：先学术文献（按第一作者姓氏、年份排序），后工程与产品文档（按 key
排序）。因此重跑本脚本不会产生无谓的编号漂移。

正文中的引用写作 `[[12]](#ref-sadowski2018)`，渲染为可点击的 `[12]`。链接目标里带 key，
使得「编号 ↔ 文献」这一映射本身可被 verify.py 核对，而不是只能靠人眼比对。

用法：
    python3 scripts/gen_references.py            # 生成并回填
    python3 scripts/gen_references.py --check    # 只检查回填结果是否已是最新
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFS = json.loads((ROOT / "lit" / "references.json").read_text())
REPORT = ROOT / "report.md"
BEGIN, END = "<!--REFS:BEGIN-->", "<!--REFS:END-->"

VENUE_FIX = {
    "ESEC/SIGSOFT FSE": "ESEC/FSE",
    "Empir. Softw. Eng.": "Empirical Software Engineering",
}


def surname(name: str) -> str:
    """取姓氏用于排序。DBLP 会给重名者附加编号（如 `Yue Yu 0001`），需剔除。"""
    parts = [p for p in name.split() if not p.isdigit()]
    return parts[-1] if parts else name


def order() -> list[dict]:
    papers = [r for r in REFS if r["kind"] in ("arxiv", "pdf")]
    webs = [r for r in REFS if r["kind"] == "web"]
    papers.sort(key=lambda r: (surname(r["authors"][0]).lower(),
                               str(r.get("year") or r.get("published", "")), r["key"]))
    webs.sort(key=lambda r: r["key"])
    return papers + webs


def author_str(authors: list[str], limit: int = 6) -> str:
    """作者列表。超过 limit 位时截断为「前 limit 位 等」，与常见期刊惯例一致。"""
    clean = [re.sub(r"\s+\d{4}$", "", a) for a in authors]
    if len(clean) > limit:
        return ", ".join(clean[:limit]) + ", 等"
    return ", ".join(clean)


def entry_md(i: int, r: dict) -> str:
    n = i + 1
    key = r["key"]
    bits: list[str] = [f'<a id="ref-{key}"></a>**[{n}]** {author_str(r["authors"])}. ']
    title = (r.get("title") or r["manifest_title"]).strip()
    if r["kind"] == "web":
        bits.append(f'*{title}*. {r.get("container", "")}. ')
        bits.append(f'<{r["url"]}>（访问日期 {r["accessed"]}）。')
        bits.append("本报告所引措辞已于该日期回原文逐句复核。")
    elif r["kind"] == "arxiv":
        bits.append(f'*{title}*. arXiv:{r["arxiv_id"]}')
        if r.get("primary_category"):
            bits.append(f' [{r["primary_category"]}]')
        bits.append(f'，{r["published"]}')
        if r.get("updated") and r["updated"] != r["published"]:
            bits.append(f'（最后修订 {r["updated"]}）')
        bits.append(". ")
        if r.get("doi"):
            bits.append(f'DOI: [{r["doi"]}](https://doi.org/{r["doi"]}). ')
        bits.append(f'e-print 源码包 <{r["url"]}>，')
        bits.append(f'SHA-256 `{r["sha256"][:16]}…`（取回于 {r["accessed"]}）。')
    else:
        venue = VENUE_FIX.get(r.get("venue", ""), r.get("venue", ""))
        bits.append(f'*{title}*. {venue} {r.get("year", "")}. ')
        if r.get("doi"):
            bits.append(f'DOI: [{r["doi"]}](https://doi.org/{r["doi"]}). ')
        bits.append(f'全文 <{r["url"]}>，SHA-256 `{r["sha256"][:16]}…`（取回于 {r["accessed"]}）。')
    return "".join(bits)


def bibtex(r: dict, n: int) -> str:
    key = re.sub(r"[^\w]", "", r["key"])
    au = " and ".join(re.sub(r"\s+\d{4}$", "", a) for a in r["authors"])
    title = (r.get("title") or r["manifest_title"]).replace("{", "").replace("}", "")
    if r["kind"] == "arxiv":
        f = [f"  author       = {{{au}}}", f"  title        = {{{title}}}",
             f"  year         = {{{r['published'][:4]}}}",
             f"  eprint       = {{{r['arxiv_id']}}}", "  archivePrefix = {arXiv}"]
        if r.get("primary_category"):
            f.append(f"  primaryClass = {{{r['primary_category']}}}")
        if r.get("doi"):
            f.append(f"  doi          = {{{r['doi']}}}")
        return "@misc{" + key + ",\n" + ",\n".join(f) + "\n}"
    if r["kind"] == "web":
        f = [f"  author       = {{{au}}}", f"  title        = {{{title}}}",
             f"  howpublished = {{{r.get('container', '')}}}",
             f"  year         = {{{r.get('year', '')}}}",
             f"  url          = {{{r['url']}}}", f"  urldate      = {{{r['accessed']}}}"]
        return "@misc{" + key + ",\n" + ",\n".join(f) + "\n}"
    f = [f"  author       = {{{au}}}", f"  title        = {{{title}}}",
         f"  booktitle    = {{{VENUE_FIX.get(r.get('venue', ''), r.get('venue', ''))}}}",
         f"  year         = {{{r.get('year', '')}}}"]
    if r.get("doi"):
        f.append(f"  doi          = {{{r['doi']}}}")
    return "@inproceedings{" + key + ",\n" + ",\n".join(f) + "\n}"


def main() -> int:
    ordered = order()
    n_paper = sum(1 for r in ordered if r["kind"] != "web")
    lines = [BEGIN, "",
             f"共 {len(ordered)} 条：学术文献 {n_paper} 条（全部下载全文核对，"
             f"校验和见 [`lit/manifest.csv`](lit/manifest.csv)，逐条引文见 "
             f"[`lit/quotes.md`](lit/quotes.md)），工程惯例与产品文档 "
             f"{len(ordered) - n_paper} 条（全部于 2026-08-04 回原文逐句复核）。"
             f"著录信息由 [`scripts/fetch_citation_metadata.py`](scripts/fetch_citation_metadata.py) "
             f"自 arXiv 与 DBLP 接口取回并落盘于 [`lit/references.json`](lit/references.json)，"
             f"本表与 [`references.bib`](references.bib) 均由 "
             f"[`scripts/gen_references.py`](scripts/gen_references.py) 生成，非手写。", ""]
    lines.append("### D.1 学术文献")
    lines.append("")
    for i, r in enumerate(ordered):
        if r["kind"] == "web" and lines[-1] != "":
            pass
        if i == n_paper:
            lines += ["", "### D.2 工程惯例与产品文档", ""]
        lines.append(entry_md(i, r))
        lines.append("")
    lines.append(END)
    block = "\n".join(lines).rstrip() + "\n"

    text = REPORT.read_text()
    if BEGIN not in text or END not in text:
        print("report.md 中缺少 <!--REFS:BEGIN--> / <!--REFS:END--> 标记", file=sys.stderr)
        return 2
    new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), block.rstrip(), text, flags=re.S)

    bib = "\n\n".join(bibtex(r, i + 1) for i, r in enumerate(ordered)) + "\n"
    bib = ("% 由 scripts/gen_references.py 从 lit/references.json 生成，请勿手工编辑。\n"
           "% 著录信息取自 arXiv Atom API 与 DBLP 检索 API，取回日期见各条 urldate 或"
           " lit/references.json。\n\n") + bib

    if "--check" in sys.argv:
        ok = (new == text) and (ROOT / "references.bib").read_text() == bib
        print("参考文献表与 BibTeX 已是最新" if ok else "参考文献表或 BibTeX 已过期，请重跑本脚本")
        return 0 if ok else 1

    REPORT.write_text(new)
    (ROOT / "references.bib").write_text(bib)
    print(f"参考文献 {len(ordered)} 条已回填 report.md，并写入 references.bib")
    for i, r in enumerate(ordered):
        print(f"  [{i+1:>2}] {r['key']:<20} {surname(r['authors'][0])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
