#!/usr/bin/env python3
"""为 lit/manifest.csv 中的每篇文献取回完整著录信息，写入 lit/references.json。

动机。本仓库要求正文中的每个数字都可追溯到落盘数据；参考文献理应受同一标准约束。手写
作者名与出版信息既不可复核，也容易在转述中失真——这正是本报告在 §3.5 对文献数值所反对
的做法。因此著录信息一律从权威接口取回并落盘，附带来源与取回日期：

  * arXiv 条目  → arXiv Atom API（作者、标题、首次提交日期、DOI、分类）
  * 非 arXiv 条目 → DBLP 检索 API（作者、会议/期刊、年份、DOI），按标题匹配
  * 网页文档     → 不存在书目接口，由 WEB_SOURCES 手工著录，但必须记录访问日期，
                   且其被引用的原文措辞已在正文中逐字给出

用法：
    python3 scripts/fetch_citation_metadata.py [--accessed YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIT = ROOT / "lit"

# 网页文档：无书目接口，手工著录。每条的被引措辞均已在 report.md 中逐字给出，
# 因此其可核对性由「原文引语 + URL + 访问日期」三者共同承担。
WEB_SOURCES: list[dict] = [
    {"key": "google-standard", "kind": "web",
     "author": "Google", "year": "2026",
     "title": "The Standard of Code Review", "container": "Google Engineering Practices",
     "url": "https://google.github.io/eng-practices/review/reviewer/standard.html"},
    {"key": "nodejs-collaborator", "kind": "web",
     "author": "Node.js Project", "year": "2026",
     "title": "Collaborator Guide", "container": "nodejs/node",
     "url": "https://github.com/nodejs/node/blob/main/doc/contributing/collaborator-guide.md"},
    {"key": "k8s-pr", "kind": "web",
     "author": "Kubernetes Project", "year": "2026",
     "title": "Pull Requests", "container": "kubernetes.dev Contributor Guide",
     "url": "https://www.kubernetes.dev/docs/guide/pull-requests/"},
    {"key": "apache-voting", "kind": "web",
     "author": "The Apache Software Foundation", "year": "2026",
     "title": "Apache Voting Process", "container": "apache.org",
     "url": "https://www.apache.org/foundation/voting.html"},
    {"key": "gitlab-review", "kind": "web",
     "author": "GitLab", "year": "2026",
     "title": "Code Review Guidelines", "container": "GitLab Development Documentation",
     "url": "https://docs.gitlab.com/development/code_review/"},
    {"key": "rfcbot", "kind": "web",
     "author": "rust-lang", "year": "2026",
     "title": "rfcbot-rs", "container": "GitHub",
     "url": "https://github.com/rust-lang/rfcbot-rs"},
    {"key": "cc-code-review", "kind": "web",
     "author": "Anthropic", "year": "2026",
     "title": "Code Review", "container": "Claude Code Documentation",
     "url": "https://code.claude.com/docs/en/code-review"},
    {"key": "cc-github-actions", "kind": "web",
     "author": "Anthropic", "year": "2026",
     "title": "Claude Code GitHub Actions", "container": "Claude Code Documentation",
     "url": "https://code.claude.com/docs/en/github-actions"},
    {"key": "cc-hooks", "kind": "web",
     "author": "Anthropic", "year": "2026",
     "title": "Hooks Reference", "container": "Claude Code Documentation",
     "url": "https://code.claude.com/docs/en/hooks"},
    {"key": "codex-github", "kind": "web",
     "author": "OpenAI", "year": "2026",
     "title": "Codex GitHub Integration", "container": "OpenAI Codex Documentation",
     "url": "https://learn.chatgpt.com/codex/third-party/github"},
    {"key": "codex-review-usecase", "kind": "web",
     "author": "OpenAI", "year": "2026",
     "title": "GitHub Code Reviews", "container": "OpenAI Codex Documentation",
     "url": "https://learn.chatgpt.com/use-cases/github-code-reviews"},
    {"key": "github-citation", "kind": "web",
     "author": "GitHub", "year": "2026",
     "title": "About CITATION files", "container": "GitHub Docs",
     "url": "https://docs.github.com/en/repositories/managing-your-repositorys-settings-"
            "and-features/customizing-your-repository/about-citation-files"},
]


# manifest.csv 中被缩写的标题，检索时改用出版方的完整标题，否则 Jaccard 会因长度差过大而未命中。
TITLE_OVERRIDES = {
    "thongtanunam2016": "Review participation in modern code review An empirical study of the "
                        "android Qt and OpenStack projects",
}


def curl(url: str, tries: int = 6, expect: str = "") -> str:
    """取回 url。expect 给出响应必须以之开头的字符（DBLP 限流时会返回 HTML 而非 JSON，
    若不校验就会在下游炸成 JSONDecodeError 并中断整批）。"""
    last = ""
    for attempt in range(tries):
        p = subprocess.run(["curl", "-sL", "--max-time", "40", url],
                           capture_output=True, text=True)
        body = p.stdout.strip()
        if p.returncode == 0 and body and (not expect or body[0] in expect):
            return p.stdout
        last = (body[:80] or p.stderr.strip()[:80])
        time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"取回失败：{url}（最后一次响应：{last!r}）")


def fetch_arxiv(arxiv_id: str) -> dict:
    """arXiv Atom API。取作者、标题、首次提交日期、DOI（若已发表）与主分类。"""
    xml = curl(f"https://export.arxiv.org/api/query?id_list={arxiv_id}&max_results=1")
    entry = xml.split("<entry>")[-1]

    def one(tag: str) -> str:
        m = re.search(rf"<{tag}>(.*?)</{tag}>", entry, re.S)
        return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

    return {
        "authors": re.findall(r"<name>(.*?)</name>", entry),
        "title": one("title"),
        "published": one("published")[:10],
        "updated": one("updated")[:10],
        "doi": one("arxiv:doi"),
        "primary_category": (re.search(r'<arxiv:primary_category[^>]*term="([^"]+)"', entry)
                             or re.match("", "")) and
                            re.search(r'<arxiv:primary_category[^>]*term="([^"]+)"',
                                      entry).group(1),
        "source_api": "arxiv",
    }


def fetch_dblp(title: str) -> dict:
    """DBLP 检索 API。按标题取最佳匹配。

    相似度必须是**对称**的（Jaccard），不能只算「查询词有多少出现在命中标题里」：后者对
    包含查询词的更长标题恒为 1.0，会把不同的论文判为命中。本项目实际踩过这个坑——
    「Review Participation in Modern Code Review」曾被单向覆盖率匹配到另一篇标题更长、
    恰好包含全部查询词的论文（见 report.md §9.4 的 C1）。
    """
    q = urllib.parse.quote(re.sub(r"[^\w ]", " ", title))
    data = json.loads(curl(f"https://dblp.org/search/publ/api?q={q}&format=json&h=8",
                          expect="{["))
    hits = data.get("result", {}).get("hits", {}).get("hit", [])

    def norm(s: str) -> set[str]:
        s = s.replace("&apos;", "'").replace("&amp;", "&")
        return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 3}

    want = norm(title)
    best, score = None, 0.0
    for h in hits:
        info = h["info"]
        got = norm(info.get("title", ""))
        s = len(want & got) / max(1, len(want | got))          # Jaccard，双向
        if s > score:
            best, score = info, s
    if not best or score < 0.6:
        return {"source_api": "dblp", "matched": False, "match_score": round(score, 2)}
    au = best.get("authors", {}).get("author") or []
    if isinstance(au, dict):
        au = [au]
    return {
        "authors": [a["text"] for a in au],
        "title": best.get("title", "").rstrip(".").replace("&apos;", "'").replace("&amp;", "&"),
        "venue": best.get("venue", ""),
        "year": best.get("year", ""),
        "doi": best.get("doi", ""),
        "dblp_url": best.get("url", ""),
        "source_api": "dblp",
        "matched": True,
        "match_score": round(score, 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accessed", default="2026-08-04")
    args = ap.parse_args()

    rows = list(csv.DictReader((LIT / "manifest.csv").open(encoding="utf-8")))
    out: list[dict] = []
    for r in rows:
        rec = {"key": r["key"], "kind": r["kind"], "tier": int(r["tier"]),
               "manifest_title": r["title"], "url": r["url"], "sha256": r["sha256"],
               "accessed": args.accessed}
        if r["kind"] == "arxiv":
            rec["arxiv_id"] = r["key"]
            rec.update(fetch_arxiv(r["key"]))
        else:
            rec.update(fetch_dblp(TITLE_OVERRIDES.get(r["key"], r["title"])))
        out.append(rec)
        who = ", ".join(rec.get("authors", [])[:2]) or "未命中"
        print(f"  {r['key']:<16} {who}", flush=True)
        time.sleep(3.0)                      # 两个接口都要求节制请求；DBLP 更敏感

    for w in WEB_SOURCES:
        out.append({**w, "accessed": args.accessed, "tier": 1,
                    "authors": [w["author"]], "source_api": "manual"})

    (LIT / "references.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    n_ok = sum(1 for r in out if r.get("authors"))
    print(f"\n写入 lit/references.json：{len(out)} 条，其中 {n_ok} 条有作者信息")
    for r in out:
        if not r.get("authors"):
            print(f"  !! 缺作者：{r['key']}（match_score={r.get('match_score')}）")


if __name__ == "__main__":
    main()
