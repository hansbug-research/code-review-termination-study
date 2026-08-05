#!/usr/bin/env python3
"""D9：收到过正式阻塞（CHANGES_REQUESTED）的 PR 最终去向。

动机。报告的 §6 归纳出四类「让循环变短」的装置，但循环没能变短时会发生什么，前几版只在
方案章里用一个四元组带过，且该四元组未经任何实测。本数据集直接测这件事：一个 PR 一旦被
正式阻塞，它后来怎么了。

四个子集：

  d9_base       各仓库 merged / closed-unmerged 的总量。D1 与 D2 是两个独立抽样框
                （各取最近 100 个），因此不能直接相除得到条件概率；必须用总体基数加权。
  d9_blocked_closed   D2 中曾被阻塞且最终未合并的 PR，取其完整的关闭/重开事件、关闭者、
                以及交叉引用（用于判断「补丁死了但工作被后续 PR 接续」）。
  d9_blocked_merged   D1 中曾被阻塞但最终合并的 PR，取其 review 时间线，用于回答
                「被阻塞的 PR 是怎么走出来的」——这是另外半边，缺了它就只看见了死亡。
  d9_super      对上述关闭的 PR，检测是否存在「被取代」的痕迹（关闭前后引用了别的 PR）。

用法：
    python3 scripts/collect_d9_blocked_fate.py
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
# 与 D1/D2 同一批仓库。pytorch 的 search 索引在本项目多次被证实不可靠（见 report.md §5.3），
# 故基数一项排除 pytorch，但其 PR 级数据仍然采集。
REPOS = ["kubernetes/kubernetes", "rust-lang/rust", "nodejs/node",
         "pytorch/pytorch", "python/cpython"]
BASE_UNRELIABLE = {"pytorch/pytorch"}
BASE_SINCE = "2025-08-01"
BATCH = 8

GAPS: list[dict] = []


def gh(args: list[str], tries: int = 6, label: str = "") -> str:
    last = ""
    for attempt in range(tries):
        p = subprocess.run(["gh", *args], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout
        last = p.stderr.strip()[:120]
        time.sleep(min(2 ** attempt, 30))
    GAPS.append({"label": label, "error": last,
                 "at": datetime.utcnow().isoformat() + "Z"})
    return ""


def graphql(query: str, label: str) -> dict:
    out = gh(["api", "graphql", "-f", f"query={query}"], label=label)
    return json.loads(out)["data"] if out else {}


def cr_count(pr: dict) -> int:
    return sum(1 for r in pr["reviews"]["nodes"] if r["state"] == "CHANGES_REQUESTED")


PR_FRAG = """
    number title state merged createdAt closedAt mergedAt additions deletions
    author {{ login }}
    comments {{ totalCount }}
    reviews(first: 100) {{ totalCount nodes {{ state submittedAt author {{ login }} }} }}
    timelineItems(first: 100, itemTypes: [CLOSED_EVENT, REOPENED_EVENT,
                                          CROSS_REFERENCED_EVENT, CONNECTED_EVENT]) {{
      totalCount
      nodes {{
        __typename
        ... on ClosedEvent {{ createdAt actor {{ login }} }}
        ... on ReopenedEvent {{ createdAt actor {{ login }} }}
        ... on CrossReferencedEvent {{ createdAt willCloseTarget
             source {{ ... on PullRequest {{ number merged state repository {{ nameWithOwner }} }} }} }}
      }}
    }}
"""


def fetch_prs(items: list[tuple[str, int]], label: str) -> dict:
    """按 (仓库, PR 号) 精确取回，保证与 D1/D2 是同一批对象。"""
    out: dict[str, dict] = {}
    for i in range(0, len(items), BATCH):
        chunk = items[i:i + BATCH]
        parts = []
        for j, (repo, n) in enumerate(chunk):
            o, nm = repo.split("/")
            parts.append(f'p{j}: repository(owner: "{o}", name: "{nm}") '
                         f'{{ pullRequest(number: {n}) {{ {PR_FRAG.format()} }} }}')
        data = graphql("{" + "\n".join(parts) + "}", f"{label}:{i}")
        for j, (repo, n) in enumerate(chunk):
            node = (data.get(f"p{j}") or {}).get("pullRequest")
            if node:
                out[f"{repo}#{n}"] = {"repo": repo, **node}
        print(f"  {label}: {len(out)}/{len(items)}", flush=True)
        time.sleep(1)
    return out


def main() -> None:
    d1 = json.loads((RAW / "d1_merged_prs.json").read_text())
    d2 = json.loads((RAW / "d2_closed_prs.json").read_text())

    blocked_closed = [(r, p["number"]) for r, prs in d2.items() for p in prs
                      if p.get("closedAt") and not p.get("mergedAt") and cr_count(p) >= 1]
    blocked_merged = [(r, p["number"]) for r, prs in d1.items() for p in prs
                      if p.get("mergedAt") and cr_count(p) >= 1]
    print(f"D2 中曾被阻塞且未合并：{len(blocked_closed)} 个")
    print(f"D1 中曾被阻塞但已合并：{len(blocked_merged)} 个")

    # ---- 基数：用于把两个独立抽样框的比率加权成条件概率
    base: dict[str, dict] = {}
    for repo in REPOS:
        if repo in BASE_UNRELIABLE:
            base[repo] = {"repo": repo, "reliable": False,
                          "note": "search 索引对该仓库不可靠，见 report.md §5.3"}
            continue
        m = gh(["api", "-X", "GET", "search/issues", "-f",
                f"q=repo:{repo} is:pr is:merged created:>={BASE_SINCE}",
                "--jq", ".total_count"], label=f"base:m:{repo}").strip()
        time.sleep(2)
        c = gh(["api", "-X", "GET", "search/issues", "-f",
                f"q=repo:{repo} is:pr is:unmerged is:closed created:>={BASE_SINCE}",
                "--jq", ".total_count"], label=f"base:c:{repo}").strip()
        time.sleep(2)
        base[repo] = {"repo": repo, "reliable": True, "since": BASE_SINCE,
                      "merged_total": int(m or 0), "closed_unmerged_total": int(c or 0)}
        print(f"  基数 {repo}: merged={m} closed_unmerged={c}", flush=True)

    payload = {
        "baseline_date": json.loads((RAW / "manifest.json").read_text()).get("baseline_date", ""),
        "base_since": BASE_SINCE,
        "base": base,
        "blocked_closed": fetch_prs(blocked_closed, "blocked_closed"),
        "blocked_merged": fetch_prs(blocked_merged, "blocked_merged"),
        "gaps": GAPS,
    }
    (RAW / "d9_blocked_fate.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print(f"\n写入 raw/d9_blocked_fate.json"
          f"（关闭 {len(payload['blocked_closed'])} + 合并 {len(payload['blocked_merged'])}"
          f"，缺口 {len(GAPS)}）")


if __name__ == "__main__":
    main()
