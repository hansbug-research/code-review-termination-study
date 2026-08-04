#!/usr/bin/env python3
"""D1-D8 原始数据采集器。

全部数据经 GitHub GraphQL API 取得，凭据由本机 `gh` CLI 提供（需 `gh auth status` 已登录）。
每个数据集写入 raw/<name>.json，并在 raw/manifest.json 记录逐次查询的原文、时间戳与返回条数，
使任何结论都能追溯到一次具体的 API 调用。

用法：
    python3 scripts/collect.py            # 全量采集
    python3 scripts/collect.py d1 d3      # 只采指定数据集
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# 基准日：全部数据在此日采集完成。改动此常量不会改变已落盘数据，仅用于报告标注。
BASELINE_DATE = "2026-08-04"

# D1/D2 的仓库集合。选取标准见 report.md §3.1：GitHub 上长期活跃、贡献者规模大、
# review 流程有公开成文规范、且分属不同治理模型（企业主导 / 基金会 / BDFL / 厂商主导）。
MATURE_REPOS = [
    ("kubernetes", "kubernetes"),
    ("rust-lang", "rust"),
    ("nodejs", "node"),
    ("pytorch", "pytorch"),
    ("python", "cpython"),
]

# D3 的 agent 身份。只有以 GitHub App 身份推送 PR 的 agent 才可被 `author:app/<slug>` 检索；
# Codex 与 Cursor 的 PR 以人类账号署名，结构上不可识别（见 report.md §3.5 局限性）。
AGENT_APPS = [
    "copilot-swe-agent",
    "devin-ai-integration",
    "claude",
    "google-labs-jules",
]

# D4 的 revert 率窗口。起点取 2026-02-01，使窗口长度（约 6 个月）足够容纳低频事件。
REVERT_REPOS = [
    ("kubernetes", "kubernetes"),
    ("rust-lang", "rust"),
    ("nodejs", "node"),
    ("python", "cpython"),
]
REVERT_SINCE = "2026-02-01"

MANIFEST: list[dict] = []


def gh_graphql(query: str, tries: int = 8, label: str = "") -> dict:
    """执行一次 GraphQL 查询。GitHub 的 search/timeline 端点会间歇性返回 502，故带指数退避重试。"""
    last = ""
    for attempt in range(1, tries + 1):
        proc = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query}"],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            try:
                data = json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                last = f"JSONDecodeError: {exc}"
            else:
                if "data" in data and data["data"] is not None:
                    MANIFEST.append({
                        "label": label,
                        "query": " ".join(query.split()),
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "attempts": attempt,
                    })
                    return data["data"]
                last = json.dumps(data.get("errors", data))[:300]
        else:
            last = (proc.stderr or proc.stdout)[:300]
        if attempt < tries:
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"GraphQL 失败（{label}），最后一次错误：{last}")


# 采集缺口。任何未能取到的仓库/查询都登记在此并写入 manifest，使「数据不全」永远是显式的，
# 而不是静默变成一个偏小的分母。
GAPS: list[dict] = []


def safe(gap_label: str, fn, *args, **kwargs):
    """执行一个采集动作；失败时登记缺口并返回 None，不中断整批采集。"""
    try:
        return fn(*args, **kwargs)
    except RuntimeError as exc:
        GAPS.append({"label": gap_label, "error": str(exc)[:300],
                     "at": datetime.now(timezone.utc).isoformat()})
        print(f"    !! 缺口 {gap_label}: {exc}")
        return None


PR_FIELDS = """
  number
  createdAt
  closedAt
  mergedAt
  additions
  deletions
  changedFiles
  commits { totalCount }
  comments { totalCount }
  labels(first: 30) { nodes { name } }
  reviews(first: 100) { totalCount nodes { state author { login } submittedAt } }
"""


def _load(name: str) -> dict:
    p = RAW / name
    return json.loads(p.read_text()) if p.exists() else {}


def d1_merged() -> None:
    """D1：成熟仓库最近 100 个已合并 PR 的 review 轮次结构。"""
    out = _load("d1_merged_prs.json")
    for owner, name in MATURE_REPOS:
        if f"{owner}/{name}" in out:
            continue
        q = f"""query {{ repository(owner: "{owner}", name: "{name}") {{
            pullRequests(states: MERGED, first: 100, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
              nodes {{ {PR_FIELDS} }} }} }} }}"""
        data = safe(f"d1:{owner}/{name}", gh_graphql, q, label=f"d1:{owner}/{name}")
        if data is None:
            continue
        nodes = data["repository"]["pullRequests"]["nodes"]
        out[f"{owner}/{name}"] = nodes
        print(f"  D1 {owner}/{name}: {len(nodes)}")
    (RAW / "d1_merged_prs.json").write_text(json.dumps(out, ensure_ascii=False))


def d2_closed() -> None:
    """D2：同批仓库最近 100 个「已关闭但未合并」PR，用于观测超时/放弃这一终止路径。"""
    out = _load("d2_closed_prs.json")
    for owner, name in MATURE_REPOS:
        if f"{owner}/{name}" in out:
            continue
        q = f"""query {{ repository(owner: "{owner}", name: "{name}") {{
            pullRequests(states: CLOSED, first: 100, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
              nodes {{ {PR_FIELDS} }} }} }} }}"""
        data = safe(f"d2:{owner}/{name}", gh_graphql, q, label=f"d2:{owner}/{name}")
        if data is None:
            continue
        nodes = data["repository"]["pullRequests"]["nodes"]
        out[f"{owner}/{name}"] = nodes
        print(f"  D2 {owner}/{name}: {len(nodes)}")
    (RAW / "d2_closed_prs.json").write_text(json.dumps(out, ensure_ascii=False))


# search 端点单次要展开 100 个 PR；若每个再取 100 条 review，节点总数足以让服务端返回 502。
# 故为 search 单独定义轻量字段集：review 上限 40（远高于观测到的中位数），并省去 labels
# （D3 的分析不使用标签）。
PR_FIELDS_SEARCH = """
  number
  createdAt
  closedAt
  mergedAt
  additions
  deletions
  changedFiles
  commits { totalCount }
  comments { totalCount }
  reviews(first: 40) { totalCount nodes { state author { login } } }
"""


def _search_prs(search_query: str, pages: int, label: str) -> list[dict]:
    """分页拉取 search 结果。GitHub search 端点硬上限 1000 条，故 pages 最大取 10。"""
    nodes: list[dict] = []
    cursor = "null"
    for page in range(pages):
        q = f"""query {{ search(query: "{search_query}", type: ISSUE, first: 100, after: {cursor}) {{
            pageInfo {{ endCursor hasNextPage }}
            nodes {{ ... on PullRequest {{
              repository {{ nameWithOwner stargazerCount }}
              {PR_FIELDS_SEARCH} }} }} }} }}"""
        data = safe(f"{label}:p{page + 1}", gh_graphql, q, tries=4,
                    label=f"{label}:p{page + 1}")
        if data is None:
            break
        got = [n for n in data["search"]["nodes"] if n]
        nodes.extend(got)
        info = data["search"]["pageInfo"]
        if not info["hasNextPage"] or not info["endCursor"]:
            break
        cursor = f'"{info["endCursor"]}"'
    return nodes


def d3_agent_prs() -> None:
    """D3：以 GitHub App 身份署名的 agent 所写 PR，已合并与已关闭未合并两支。"""
    out = _load("d3_agent_prs.json")
    for app in AGENT_APPS:
        if app in out:
            continue
        merged = _search_prs(
            f"is:pr author:app/{app} is:merged sort:updated-desc", pages=6, label=f"d3m:{app}")
        closed = _search_prs(
            f"is:pr author:app/{app} is:closed is:unmerged sort:updated-desc", pages=2, label=f"d3c:{app}")
        out[app] = {"merged": merged, "closed_unmerged": closed}
        print(f"  D3 {app}: merged={len(merged)} closed={len(closed)}")
    (RAW / "d3_agent_prs.json").write_text(json.dumps(out, ensure_ascii=False))


def d4_reverts() -> None:
    """D4：revert PR 占已合并 PR 的比例，作为「先合并、事后修/回滚」这一策略的代价估计。"""
    out = _load("d4_reverts.json")
    for owner, name in REVERT_REPOS:
        repo = f"{owner}/{name}"
        if repo in out:
            continue
        base = f"repo:{repo} is:pr is:merged merged:>{REVERT_SINCE}"
        tot = gh_graphql(
            f'query {{ search(query: "{base}", type: ISSUE, first: 1) {{ issueCount }} }}',
            label=f"d4tot:{repo}")["search"]["issueCount"]
        rev = gh_graphql(
            f'query {{ search(query: "{base} Revert in:title", type: ISSUE, first: 1) {{ issueCount }} }}',
            label=f"d4rev:{repo}")["search"]["issueCount"]
        out[repo] = {"merged_total": tot, "revert_titled": rev, "since": REVERT_SINCE}
        print(f"  D4 {repo}: {rev}/{tot}")
    (RAW / "d4_reverts.json").write_text(json.dumps(out, ensure_ascii=False))


CASES = [
    ("rust-lang", "rust", 148190, "case_a"),
    ("dotnet", "runtime", 131642, "case_b"),
]


def d5_cases() -> None:
    """D5/D6：两个案例 PR 的完整事件流（review、标签变更、评论、commit、review thread）。"""
    out = _load("d5_cases.json")
    for owner, name, number, key in CASES:
        if key in out:
            continue
        q = f"""query {{ repository(owner: "{owner}", name: "{name}") {{
            pullRequest(number: {number}) {{
              number title createdAt mergedAt additions deletions changedFiles
              author {{ login }}
              commits(first: 100) {{ totalCount nodes {{ commit {{ committedDate messageHeadline }} }} }}
              reviews(first: 100) {{ totalCount nodes {{ state author {{ login }} submittedAt bodyText }} }}
              reviewThreads(first: 100) {{ totalCount nodes {{ isResolved isOutdated
                comments(first: 1) {{ nodes {{ author {{ login }} bodyText createdAt }} }} }} }}
              comments(first: 100) {{ nodes {{ author {{ login }} createdAt bodyText }} }} }} }} }}"""
        data = gh_graphql(q, label=f"d5:{owner}/{name}#{number}")
        pr = data["repository"]["pullRequest"]
        # 标签事件必须单独取：与 ISSUE_COMMENT 混在同一个 timelineItems 连接里时，评论会占满
        # 分页上限并把后段的标签事件挤掉，导致状态机时序数据静默缺尾。
        labels: list[dict] = []
        cursor = "null"
        while True:
            lq = f"""query {{ repository(owner: "{owner}", name: "{name}") {{
                pullRequest(number: {number}) {{
                  timelineItems(first: 100, after: {cursor},
                                itemTypes: [LABELED_EVENT, UNLABELED_EVENT]) {{
                    pageInfo {{ endCursor hasNextPage }}
                    nodes {{ __typename
                      ... on LabeledEvent {{ label {{ name }} createdAt }}
                      ... on UnlabeledEvent {{ label {{ name }} createdAt }} }} }} }} }} }}"""
            ld = gh_graphql(lq, label=f"d5labels:{owner}/{name}#{number}")
            conn = ld["repository"]["pullRequest"]["timelineItems"]
            labels.extend(conn["nodes"])
            if not conn["pageInfo"]["hasNextPage"]:
                break
            cursor = f'"{conn["pageInfo"]["endCursor"]}"'
        pr["labelEvents"] = labels
        out[key] = {"repo": f"{owner}/{name}", "pr": pr}
        print(f"  D5 {key} {owner}/{name}#{number}: reviews={pr['reviews']['totalCount']} "
              f"threads={pr['reviewThreads']['totalCount']}")
    (RAW / "d5_cases.json").write_text(json.dumps(out, ensure_ascii=False))


def d7_bot_review_text() -> None:
    """D7：D3 中位于成熟仓库（star>=500）的 agent PR 上，全部由 bot 提交的 review 正文。

    用于回答「AI reviewer 的输出里有多少是实质内容」。依赖 d3 已采集完成。
    """
    d3 = json.loads((RAW / "d3_agent_prs.json").read_text())
    targets = []
    for app, buckets in d3.items():
        for pr in buckets["merged"]:
            if pr["repository"]["stargazerCount"] >= 500:
                targets.append((app, pr["repository"]["nameWithOwner"], pr["number"]))
    seen, uniq = set(), []
    for app, repo, num in targets:
        if (repo, num) not in seen:
            seen.add((repo, num))
            uniq.append((app, repo, num))
    print(f"  D7 目标 PR：{len(uniq)}")
    out = []
    for app, repo, num in uniq:
        owner, name = repo.split("/")
        q = f"""query {{ repository(owner: "{owner}", name: "{name}") {{
            pullRequest(number: {num}) {{ reviews(first: 100) {{ nodes {{
              author {{ login }} state bodyText }} }} }} }} }}"""
        try:
            data = gh_graphql(q, label=f"d7:{repo}#{num}")
        except RuntimeError as exc:
            print(f"    跳过 {repo}#{num}：{exc}")
            continue
        for r in data["repository"]["pullRequest"]["reviews"]["nodes"]:
            out.append({
                "agent_app": app, "repo": repo, "number": num,
                "reviewer": r["author"]["login"] if r["author"] else None,
                "state": r["state"], "body": r["bodyText"] or "",
            })
    (RAW / "d7_bot_review_text.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"  D7 review 记录：{len(out)}")


DATASETS = {
    "d1": d1_merged, "d2": d2_closed, "d3": d3_agent_prs,
    "d4": d4_reverts, "d5": d5_cases, "d7": d7_bot_review_text,
}


def main() -> None:
    which = [a.lower() for a in sys.argv[1:]] or list(DATASETS)
    unknown = [w for w in which if w not in DATASETS]
    if unknown:
        raise SystemExit(f"未知数据集：{unknown}；可选 {list(DATASETS)}")
    for key in which:
        print(f"[{key}] 采集中……")
        DATASETS[key]()
    man_path = RAW / "manifest.json"
    prev = json.loads(man_path.read_text())["calls"] if man_path.exists() else []
    man_path.write_text(json.dumps({
        "baseline_date": BASELINE_DATE,
        "collected_by": os.environ.get("GH_LOGIN", "gh CLI 当前账号"),
        "datasets_this_run": which,
        "gaps": GAPS,
        "calls": prev + MANIFEST,
    }, ensure_ascii=False, indent=2))
    print(f"完成。本次 API 调用 {len(MANIFEST)} 次，累计 {len(prev) + len(MANIFEST)} 次。")


if __name__ == "__main__":
    main()
