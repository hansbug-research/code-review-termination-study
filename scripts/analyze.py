#!/usr/bin/env python3
"""从 raw/ 计算全部统计量，输出 derived/tables/*.csv（可复算表）与 derived/stats.json。

报告正文中的**每一个**数字都必须来自 derived/stats.json，由 scripts/verify.py 逐条比对。
本脚本不访问网络，可在任意时刻重跑并得到与落盘原始数据一致的结果。

用法：
    python3 scripts/analyze.py
"""
from __future__ import annotations

import csv
import json
import re
import statistics as st
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
DER = ROOT / "derived"
TAB = DER / "tables"
TAB.mkdir(parents=True, exist_ok=True)

S: dict = {}          # 扁平统计量命名空间，落盘为 derived/stats.json
BOT_RE = re.compile(r"(\[bot\]|bot$|^bot|rabbit|greptile|copilot-pull|copilot-swe|sourcery|codacy|"
                    r"deepsource|snyk|renovate|dependabot|mergebot|github-actions|azure-pipelines|"
                    r"policy-service|rustbot|prow|k8s-ci|pytorch)", re.I)
# 「reviewer 未能产出任何实质内容」的机械失败特征。仅匹配显式自述失败的模板句，
# 不做语义判断，故这是实质内容占比的**上界**估计（真实的空洞评论无法用正则识别）。
MALFUNCTION_RE = re.compile(
    r"(unable to review|no eligible user to bill|could not review|review (was )?skipped|"
    r"encountered an error|timed out|quota|rate limit)", re.I)
STALE_RE = re.compile(r"(stale|inactive|rotten|lifecycle)", re.I)


def load(name: str):
    p = RAW / name
    return json.loads(p.read_text()) if p.exists() else None


def ts(x: str | None) -> datetime | None:
    return datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ") if x else None


def q(vals: list[float], p: float) -> float:
    """分位数（最近秩法）。空序列返回 0，使缺数据表现为 0 而非异常。"""
    if not vals:
        return 0.0
    s = sorted(vals)
    return float(s[min(len(s) - 1, int(len(s) * p))])


def med(vals: list[float]) -> float:
    return float(st.median(vals)) if vals else 0.0


def pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 2) if den else 0.0


def write_table(name: str, rows: list[dict], fields: list[str]) -> None:
    with (TAB / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def cr_count(pr: dict) -> int:
    return sum(1 for r in pr["reviews"]["nodes"] if r["state"] == "CHANGES_REQUESTED")


def approved_count(pr: dict) -> int:
    return sum(1 for r in pr["reviews"]["nodes"] if r["state"] == "APPROVED")


def labels_of(pr: dict) -> list[str]:
    """D3 的 search 字段集不含 labels，故统一经此访问，缺失时视为空列表。"""
    return [l["name"] for l in pr.get("labels", {}).get("nodes", [])]


def has_bot_reviewer(pr: dict) -> bool:
    return any(r["author"] and BOT_RE.search(r["author"]["login"])
               for r in pr["reviews"]["nodes"])


def human_reviewers(pr: dict) -> set[str]:
    return {r["author"]["login"] for r in pr["reviews"]["nodes"]
            if r["author"] and not BOT_RE.search(r["author"]["login"])}


# 「旁路批准」判据：批准事实存在，但不经由 GitHub review 对象，因而不计入 reviews.totalCount。
# 三条通道各由一个可在落盘数据上直接复核的标记识别：
#   1) Prow 的 `/lgtm` 指令 —— 机器人据此打 `lgtm` 标签（kubernetes 系）
#   2) bors 合并队列 —— 入队需 reviewer 显式 `@bors r+`，痕迹为 `S-waiting-on-bors` /
#      `merged-by-bors` 标签；`rollup` 则是若干**已批准** PR 的聚合（rust-lang 系）
#   3) 自动 backport —— 由 `miss-islington` 提交的、对已合并且已批准变更的移植（cpython）
# 剩余部分记为「未识别到批准痕迹」而非「无人过目」：本判据只能证实旁路批准的存在，
# 不能证伪它，故该桶是门禁缺失的**上界**。该判据只在 D1 上可用（D3 的 search 字段集不含
# labels，亦无作者身份），故跨组对照另用通道无关的严格指标 pct_zero_review_and_comment。
OFFCHANNEL_LABELS = {"lgtm", "rollup", "s-waiting-on-bors", "merged-by-bors"}
OFFCHANNEL_AUTHORS = {"miss-islington"}


def offchannel_approved(pr: dict, author: str | None) -> bool:
    return (bool(OFFCHANNEL_LABELS & {n.lower() for n in labels_of(pr)})
            or (author in OFFCHANNEL_AUTHORS))


# ---------------------------------------------------------------- D1
def analyze_d1() -> None:
    data = load("d1_merged_prs.json") or {}
    rows, pooled = [], []
    for repo, prs in data.items():
        prs = [p for p in prs if p.get("mergedAt")]
        pooled.extend(prs)
        hours = [(ts(p["mergedAt"]) - ts(p["createdAt"])).total_seconds() / 3600 for p in prs]
        crs = [cr_count(p) for p in prs]
        revs = [p["reviews"]["totalCount"] for p in prs]
        rows.append({
            "repo": repo, "n": len(prs),
            "median_hours_to_merge": round(med(hours), 1),
            "median_loc_changed": int(med([p["additions"] + p["deletions"] for p in prs])),
            "median_files": int(med([p["changedFiles"] for p in prs])),
            "median_commits": int(med([p["commits"]["totalCount"] for p in prs])),
            "pct_zero_changes_requested": pct(sum(1 for c in crs if c == 0), len(crs)),
            "pct_ge1_changes_requested": pct(sum(1 for c in crs if c >= 1), len(crs)),
            "pct_ge2_changes_requested": pct(sum(1 for c in crs if c >= 2), len(crs)),
            "max_changes_requested": max(crs) if crs else 0,
            "median_review_submissions": int(med(revs)),
            "p90_review_submissions": int(q(revs, 0.9)),
            "max_review_submissions": max(revs) if revs else 0,
            # 与 D3 的 pct_zero_formal_review 同定义（reviews.totalCount == 0），
            # 使「人类 PR vs agent PR」的门禁强度对照在同一口径下可比。
            "pct_zero_formal_review": pct(sum(1 for r in revs if r == 0), len(revs)),
            "median_distinct_human_reviewers": int(med([len(human_reviewers(p)) for p in prs])),
            "median_approvals": int(med([approved_count(p) for p in prs])),
            "pct_with_bot_reviewer": pct(sum(1 for p in prs if has_bot_reviewer(p)), len(prs)),
        })
    write_table("t01_merged_pr_review_structure.csv", rows, list(rows[0]) if rows else [])
    crs = [cr_count(p) for p in pooled]
    revs = [p["reviews"]["totalCount"] for p in pooled]
    S["d1_repos"] = len(data)
    S["d1_n"] = len(pooled)
    S["d1_pooled_pct_zero_cr"] = pct(sum(1 for c in crs if c == 0), len(crs))
    S["d1_pooled_pct_ge1_cr"] = pct(sum(1 for c in crs if c >= 1), len(crs))
    S["d1_pooled_max_cr"] = max(crs) if crs else 0
    S["d1_pooled_median_reviews"] = int(med(revs))
    S["d1_pooled_pct_zero_formal_review"] = pct(sum(1 for r in revs if r == 0), len(revs))
    S["d1_pooled_pct_zero_review_and_comment"] = pct(sum(
        1 for p in pooled if p["reviews"]["totalCount"] == 0
        and p["comments"]["totalCount"] == 0), len(pooled))
    S["d1_pooled_median_loc"] = int(med([p["additions"] + p["deletions"] for p in pooled]))
    S["d1_pooled_median_hours"] = round(med(
        [(ts(p["mergedAt"]) - ts(p["createdAt"])).total_seconds() / 3600 for p in pooled]), 1)
    S["d1_pooled_median_approvals"] = int(med([approved_count(p) for p in pooled]))
    S["d1_pooled_pct_zero_approval"] = pct(
        sum(1 for p in pooled if approved_count(p) == 0), len(pooled))
    S["d1_min_pct_zero_cr"] = min(r["pct_zero_changes_requested"] for r in rows) if rows else 0
    S["d1_max_pct_zero_cr"] = max(r["pct_zero_changes_requested"] for r in rows) if rows else 0
    S["d1_by_repo"] = {r["repo"]: r for r in rows}


# ---------------------------------------------------------------- D8 × D1：旁路批准分解
def analyze_offchannel() -> None:
    """把 D1 的「零正式 review」拆成旁路批准与真正无人过目两类。

    若不做这个拆分，`reviews.totalCount == 0` 会把「经由 Prow / rollup / 自动 backport
    批准」与「无人过目」计为同一件事，而这两者对有穷性的含义正好相反：前者是批准通道的
    实现细节，后者才是门禁缺失。
    """
    d1 = load("d1_merged_prs.json") or {}
    authors = load("d8_d1_authors.json") or {}
    if not authors:
        S["d8_present"] = False
        return
    S["d8_present"] = True
    rows, pooled_zero, pooled_off, pooled_n = [], 0, 0, 0
    for repo, prs in d1.items():
        prs = [p for p in prs if p.get("mergedAt")]
        au = authors.get(repo, {})
        zero = [p for p in prs if p["reviews"]["totalCount"] == 0]
        off = [p for p in zero
               if offchannel_approved(p, au.get(str(p["number"]), {}).get("author"))]
        silent = [p for p in zero if p not in off]
        rows.append({
            "repo": repo, "n": len(prs),
            "n_zero_formal_review": len(zero),
            "pct_zero_formal_review": pct(len(zero), len(prs)),
            "n_offchannel_approved": len(off),
            "n_unattributed": len(silent),
            "pct_unattributed": pct(len(silent), len(prs)),
            "n_zero_review_and_comment": sum(
                1 for p in prs if p["reviews"]["totalCount"] == 0
                and p["comments"]["totalCount"] == 0),
            "pct_zero_review_and_comment": pct(sum(
                1 for p in prs if p["reviews"]["totalCount"] == 0
                and p["comments"]["totalCount"] == 0), len(prs)),
        })
        pooled_zero += len(zero)
        pooled_off += len(off)
        pooled_n += len(prs)
    write_table("t10_offchannel_approval_decomposition.csv", rows, list(rows[0]) if rows else [])
    S["d8_by_repo"] = {r["repo"]: r for r in rows}
    S["d8_n"] = pooled_n
    S["d8_n_zero_formal_review"] = pooled_zero
    S["d8_n_offchannel_approved"] = pooled_off
    S["d8_n_unattributed"] = pooled_zero - pooled_off
    S["d8_pct_offchannel_of_zero"] = pct(pooled_off, pooled_zero)
    S["d8_pooled_pct_unattributed"] = pct(pooled_zero - pooled_off, pooled_n)
    S["d8_k8s_lgtm_of_zero"] = sum(
        1 for p in d1.get("kubernetes/kubernetes", [])
        if p.get("mergedAt") and p["reviews"]["totalCount"] == 0
        and "lgtm" in {n.lower() for n in labels_of(p)})
    S["d8_cpython_missislington_of_zero"] = sum(
        1 for p in d1.get("python/cpython", [])
        if p.get("mergedAt") and p["reviews"]["totalCount"] == 0
        and authors.get("python/cpython", {}).get(str(p["number"]), {}).get("author")
        == "miss-islington")


# ---------------------------------------------------------------- D2
def analyze_d2() -> None:
    data = load("d2_closed_prs.json") or {}
    rows, pooled = [], []
    for repo, prs in data.items():
        prs = [p for p in prs if p.get("closedAt") and not p.get("mergedAt")]
        pooled.extend(prs)
        days = [(ts(p["closedAt"]) - ts(p["createdAt"])).total_seconds() / 86400 for p in prs]
        labeled = sum(1 for p in prs if any(STALE_RE.search(n) for n in labels_of(p)))
        rows.append({
            "repo": repo, "n": len(prs),
            "median_days_open": round(med(days), 1),
            "p90_days_open": round(q(days, 0.9), 1),
            "max_days_open": round(max(days), 1) if days else 0,
            "pct_closed_within_1day": pct(sum(1 for d in days if d < 1), len(days)),
            "pct_never_reviewed": pct(
                sum(1 for p in prs if p["reviews"]["totalCount"] == 0), len(prs)),
            "pct_ge1_changes_requested": pct(
                sum(1 for p in prs if cr_count(p) >= 1), len(prs)),
            "n_stale_or_lifecycle_labeled": labeled,
            "pct_stale_or_lifecycle_labeled": pct(labeled, len(prs)),
        })
    write_table("t02_closed_unmerged_pr_structure.csv", rows, list(rows[0]) if rows else [])
    days = [(ts(p["closedAt"]) - ts(p["createdAt"])).total_seconds() / 86400 for p in pooled]
    S["d2_n"] = len(pooled)
    S["d2_pooled_median_days"] = round(med(days), 1)
    S["d2_pooled_p90_days"] = round(q(days, 0.9), 1)
    S["d2_pooled_max_days"] = round(max(days), 1) if days else 0
    S["d2_pooled_pct_never_reviewed"] = pct(
        sum(1 for p in pooled if p["reviews"]["totalCount"] == 0), len(pooled))
    S["d2_pooled_pct_ge1_cr"] = pct(sum(1 for p in pooled if cr_count(p) >= 1), len(pooled))
    S["d2_pooled_pct_stale_labeled"] = pct(sum(
        1 for p in pooled if any(STALE_RE.search(n) for n in labels_of(p))), len(pooled))
    S["d2_by_repo"] = {r["repo"]: r for r in rows}
    S["d2_max_stale_repo"] = max(rows, key=lambda r: r["pct_stale_or_lifecycle_labeled"])["repo"] if rows else ""
    S["d2_max_stale_pct"] = max(r["pct_stale_or_lifecycle_labeled"] for r in rows) if rows else 0


# ---------------------------------------------------------------- D3
STAR_CUT = 500


def _agent_bucket_stats(prs: list[dict], merged: bool) -> dict:
    if not merged:
        days = [(ts(p["closedAt"]) - ts(p["createdAt"])).total_seconds() / 86400
                for p in prs if p.get("closedAt")]
        return {"n": len(prs), "median_days_open": round(med(days), 2),
                "pct_never_reviewed": pct(
                    sum(1 for p in prs if p["reviews"]["totalCount"] == 0), len(prs))}
    mins = [(ts(p["mergedAt"]) - ts(p["createdAt"])).total_seconds() / 60
            for p in prs if p.get("mergedAt")]
    revs = [p["reviews"]["totalCount"] for p in prs]
    return {
        "n": len(prs),
        "median_minutes_to_merge": round(med(mins), 1),
        "median_hours_to_merge": round(med(mins) / 60, 1),
        "pct_merged_under_10min": pct(sum(1 for m in mins if m < 10), len(mins)),
        "pct_merged_under_1h": pct(sum(1 for m in mins if m < 60), len(mins)),
        "pct_zero_formal_review": pct(sum(1 for r in revs if r == 0), len(revs)),
        "pct_zero_review_and_comment": pct(sum(
            1 for p in prs if p["reviews"]["totalCount"] == 0
            and p["comments"]["totalCount"] == 0), len(prs)),
        "median_review_submissions": int(med(revs)),
        "pct_ge1_changes_requested": pct(sum(1 for p in prs if cr_count(p) >= 1), len(prs)),
        "median_commits": int(med([p["commits"]["totalCount"] for p in prs])),
        "median_loc_changed": int(med([p["additions"] + p["deletions"] for p in prs])),
        "pct_with_bot_reviewer": pct(sum(1 for p in prs if has_bot_reviewer(p)), len(prs)),
    }


def analyze_d3() -> None:
    data = load("d3_agent_prs.json") or {}
    if not data:
        S["d3_present"] = False
        return
    S["d3_present"] = True
    rows, all_merged = [], []
    for app, buckets in data.items():
        merged = [p for p in buckets["merged"] if p.get("mergedAt")]
        all_merged.extend(merged)
        for label, subset in (("all", merged),
                              (f"stars_ge{STAR_CUT}",
                               [p for p in merged
                                if p["repository"]["stargazerCount"] >= STAR_CUT]),
                              (f"stars_lt{STAR_CUT}",
                               [p for p in merged
                                if p["repository"]["stargazerCount"] < STAR_CUT])):
            if not subset:
                continue
            rows.append({"agent_app": app, "stratum": label,
                         **_agent_bucket_stats(subset, merged=True)})
    fields = ["agent_app", "stratum", "n", "median_minutes_to_merge", "median_hours_to_merge",
              "pct_merged_under_10min", "pct_merged_under_1h", "pct_zero_formal_review",
              "pct_zero_review_and_comment", "median_review_submissions",
              "pct_ge1_changes_requested", "median_commits", "median_loc_changed",
              "pct_with_bot_reviewer"]
    write_table("t03_agent_pr_by_agent_and_stratum.csv", rows, fields)

    big = [p for p in all_merged if p["repository"]["stargazerCount"] >= STAR_CUT]
    small = [p for p in all_merged if p["repository"]["stargazerCount"] < STAR_CUT]
    S["d3_apps"] = sorted(data)
    S["d3_n_merged_all"] = len(all_merged)
    S["d3_n_repos"] = len({p["repository"]["nameWithOwner"] for p in all_merged})
    S["d3_pooled_all"] = _agent_bucket_stats(all_merged, merged=True)
    S["d3_pooled_mature"] = _agent_bucket_stats(big, merged=True)
    S["d3_pooled_small"] = _agent_bucket_stats(small, merged=True)
    S["d3_n_mature"] = len(big)
    S["d3_n_small"] = len(small)
    S["d3_pct_in_mature_repos"] = pct(len(big), len(all_merged))
    S["d3_mature_repo_list"] = sorted({p["repository"]["nameWithOwner"] for p in big})
    S["d3_star_cut"] = STAR_CUT
    closed_rows = []
    for app, buckets in data.items():
        cu = [p for p in buckets["closed_unmerged"] if p.get("closedAt")]
        if cu:
            closed_rows.append({"agent_app": app, **_agent_bucket_stats(cu, merged=False)})
    if closed_rows:
        write_table("t04_agent_pr_closed_unmerged.csv", closed_rows,
                    ["agent_app", "n", "median_days_open", "pct_never_reviewed"])
        S["d3_closed"] = {r["agent_app"]: r for r in closed_rows}


# ---------------------------------------------------------------- D3 聚簇敏感性
def analyze_cluster_sensitivity() -> None:
    """成熟层的仓库级聚簇诊断与留一仓库刀切。

    D3 成熟层的 78 个 PR 分布在 24 个仓库上且极不均衡，因此它们不是独立观测：任何按 PR
    计数的比率都可能由单一仓库的策略决定，而非由「仓库成熟度」这一自变量决定。此处给出
    (a) 仓库级集中度，(b) 逐仓库留一后的比率范围，(c) 以仓库为单位（每仓库一票，取该仓库
    内比率）的宏平均——后者对聚簇不敏感，是更保守的估计量。
    """
    data = load("d3_agent_prs.json") or {}
    if not data:
        return
    big = [p for app, b in data.items() for p in b["merged"]
           if p.get("mergedAt") and p["repository"]["stargazerCount"] >= STAR_CUT]
    if not big:
        return
    by_repo: dict[str, list] = {}
    for p in big:
        by_repo.setdefault(p["repository"]["nameWithOwner"], []).append(p)

    def strict_zero(prs: list) -> int:
        return sum(1 for p in prs if p["reviews"]["totalCount"] == 0
                   and p["comments"]["totalCount"] == 0)

    rows = [{"repo": r, "n": len(v), "n_zero_review_and_comment": strict_zero(v),
             "pct_zero_review_and_comment": pct(strict_zero(v), len(v)),
             "pct_zero_formal_review": pct(
                 sum(1 for p in v if p["reviews"]["totalCount"] == 0), len(v)),
             "agents": "|".join(sorted({app for app, b in data.items()
                                        for p in b["merged"]
                                        if p.get("mergedAt")
                                        and p["repository"]["nameWithOwner"] == r
                                        and p["repository"]["stargazerCount"] >= STAR_CUT}))}
            for r, v in sorted(by_repo.items(), key=lambda kv: -len(kv[1]))]
    write_table("t11_mature_stratum_repo_clustering.csv", rows, list(rows[0]))

    total, tz = len(big), strict_zero(big)
    loo = {r: pct(tz - strict_zero(v), total - len(v)) for r, v in by_repo.items()
           if total - len(v) > 0}
    worst = min(loo.items(), key=lambda kv: kv[1])
    macro = round(sum(r["pct_zero_review_and_comment"] for r in rows) / len(rows), 2)
    S["d3_mature_n_repos"] = len(by_repo)
    S["d3_mature_top_repo"] = rows[0]["repo"]
    S["d3_mature_top_repo_n"] = rows[0]["n"]
    S["d3_mature_top_repo_share_pct"] = pct(rows[0]["n"], total)
    S["d3_mature_strict_zero_n"] = tz
    S["d3_mature_strict_zero_top_repo_n"] = rows[0]["n_zero_review_and_comment"]
    S["d3_mature_strict_zero_share_in_top_repo_pct"] = pct(
        rows[0]["n_zero_review_and_comment"], tz)
    S["d3_mature_loo_min_pct"] = worst[1]
    S["d3_mature_loo_min_repo"] = worst[0]
    S["d3_mature_loo_max_pct"] = max(loo.values())
    S["d3_mature_macro_avg_strict_zero_pct"] = macro
    S["d3_mature_n_repos_with_any_strict_zero"] = sum(
        1 for r in rows if r["n_zero_review_and_comment"] > 0)

    # 对小仓库层做同样的聚簇诊断，以判断该层的比率是否也由少数仓库主导。
    small = [p for app, b in data.items() for p in b["merged"]
             if p.get("mergedAt") and p["repository"]["stargazerCount"] < STAR_CUT]
    sby: dict[str, list] = {}
    for p in small:
        sby.setdefault(p["repository"]["nameWithOwner"], []).append(p)
    stop = max(sby.items(), key=lambda kv: len(kv[1]))
    stz = strict_zero(small)
    sloo = {r: pct(stz - strict_zero(v), len(small) - len(v))
            for r, v in sby.items() if len(small) - len(v) > 0}
    S["d3_small_n_repos"] = len(sby)
    S["d3_small_top_repo_share_pct"] = pct(len(stop[1]), len(small))
    S["d3_small_loo_min_pct"] = min(sloo.values())
    S["d3_small_loo_max_pct"] = max(sloo.values())
    S["d3_small_macro_avg_strict_zero_pct"] = round(
        sum(pct(strict_zero(v), len(v)) for v in sby.values()) / len(sby), 2)


# ---------------------------------------------------------------- D4
def analyze_d4() -> None:
    data = load("d4_reverts.json") or {}
    rows = []
    tot = rev = 0
    for repo, d in sorted(data.items()):
        rows.append({"repo": repo, "since": d["since"], "merged_total": d["merged_total"],
                     "revert_titled": d["revert_titled"],
                     "revert_pct": pct(d["revert_titled"], d["merged_total"])})
        tot += d["merged_total"]
        rev += d["revert_titled"]
    write_table("t05_revert_rate.csv", rows,
                ["repo", "since", "merged_total", "revert_titled", "revert_pct"])
    S["d4_n_repos"] = len(rows)
    S["d4_merged_total"] = tot
    S["d4_revert_total"] = rev
    S["d4_pooled_pct"] = pct(rev, tot)
    S["d4_min_pct"] = min((r["revert_pct"] for r in rows), default=0)
    S["d4_max_pct"] = max((r["revert_pct"] for r in rows), default=0)
    S["d4_by_repo"] = {r["repo"]: r for r in rows}
    S["d4_since"] = rows[0]["since"] if rows else ""


# ---------------------------------------------------------------- D5 案例 A
def analyze_case_a() -> None:
    d = (load("d5_cases.json") or {}).get("case_a")
    if not d:
        return
    pr = d["pr"]
    created, merged = ts(pr["createdAt"]), ts(pr["mergedAt"])
    # labelEvents 是专门分页取得的完整标签事件流；不能用混有 ISSUE_COMMENT 的 timelineItems，
    # 那会因分页上限被评论占满而静默丢掉后段标签事件。
    labels = [n for n in pr.get("labelEvents", []) if n.get("label")]
    flow = [{"event": ("+" if n["__typename"] == "LabeledEvent" else "-") + n["label"]["name"],
             "at": n["createdAt"]} for n in labels]
    flow.sort(key=lambda f: f["at"])
    write_table("t06_case_a_label_flow.csv", flow, ["event", "at"])
    states = [f["event"][1:] for f in flow if f["event"][1:].startswith("S-")]

    # 状态占用区间：检验「任何时刻球的持有者唯一」这一常见断言是否成立。
    # 该断言若成立，则任意时刻至多有一个 S-* 标签在挂；否则存在并发占用。
    t0 = ts(flow[0]["at"]) if flow else created
    ivs, open_at = [], {}
    for f in flow:
        name = f["event"][1:]
        if not name.startswith("S-"):
            continue
        t = (ts(f["at"]) - t0).total_seconds() / 86400
        if f["event"][0] == "+":
            open_at[name] = t
        elif name in open_at:
            ivs.append((open_at.pop(name), t))
    pts = sorted({x for iv in ivs for x in iv})
    span = multi = 0.0
    for a, b in zip(pts, pts[1:]):
        mid = (a + b) / 2
        k = sum(1 for s, e in ivs if s <= mid < e)
        if k >= 1:
            span += b - a
        if k > 1:
            multi += b - a
    revs = pr["reviews"]["nodes"]
    by_state: dict[str, int] = {}
    for r in revs:
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1
    S["case_a"] = {
        "repo": d["repo"], "number": pr["number"], "title": pr["title"],
        "author": pr["author"]["login"],
        "days": round((merged - created).total_seconds() / 86400, 1),
        "loc": pr["additions"] + pr["deletions"], "files": pr["changedFiles"],
        "commits": pr["commits"]["totalCount"],
        "n_reviews": pr["reviews"]["totalCount"],
        "review_states": by_state,
        "n_approved": by_state.get("APPROVED", 0),
        "n_changes_requested": by_state.get("CHANGES_REQUESTED", 0),
        "n_label_events": len(flow),
        "n_state_label_events": len(states),
        "distinct_state_labels": sorted(set(states)),
        "n_distinct_state_labels": len(set(states)),
        "n_state_intervals": len(ivs),
        "state_covered_days": round(span, 1),
        "pct_time_multi_state": round(100.0 * multi / span, 1) if span else 0.0,
        "multi_state_days": round(multi, 1),
        "n_participants": len({r["author"]["login"] for r in revs if r["author"]}),
        "author_self_reviews": sum(
            1 for r in revs if r["author"] and r["author"]["login"] == pr["author"]["login"]),
    }


# ---------------------------------------------------------------- D5 案例 B
def analyze_case_b() -> None:
    d = (load("d5_cases.json") or {}).get("case_b")
    if not d:
        return
    pr = d["pr"]
    created, merged = ts(pr["createdAt"]), ts(pr["mergedAt"])
    revs = pr["reviews"]["nodes"]
    author = pr["author"]["login"]

    by_author: dict[str, int] = {}
    for r in revs:
        k = r["author"]["login"] if r["author"] else "?"
        by_author[k] = by_author.get(k, 0) + 1
    # 「AI reviewer」在本案例中的实际产出：逐条判断是否为机械失败模板
    ai_rev = [r for r in revs if r["author"]
              and r["author"]["login"] == "copilot-pull-request-reviewer"]
    ai_malfunction = sum(1 for r in ai_rev if MALFUNCTION_RE.search(r["bodyText"] or ""))

    threads = pr["reviewThreads"]["nodes"]
    openers: dict[str, int] = {}
    for t in threads:
        c = t["comments"]["nodes"]
        if c and c[0]["author"]:
            k = c[0]["author"]["login"]
            openers[k] = openers.get(k, 0) + 1

    commits = [c["commit"] for c in pr["commits"]["nodes"]]
    issue_comments = [c for c in pr.get("comments", {}).get("nodes", []) if c.get("author")]
    revert_commits = [c["messageHeadline"] for c in commits
                      if re.search(r"^(revert|restore)\b", c["messageHeadline"], re.I)]
    write_table("t07_case_b_commits.csv",
                [{"committedDate": c["committedDate"], "messageHeadline": c["messageHeadline"]}
                 for c in commits], ["committedDate", "messageHeadline"])

    # agent 对 review 的响应延迟：每条非 agent 的 review 之后，agent 的下一次 review 回复间隔
    others = sorted((ts(r["submittedAt"]) for r in revs
                     if r["author"] and r["author"]["login"] != author), reverse=False)
    agent_ts = sorted(ts(r["submittedAt"]) for r in revs
                      if r["author"] and r["author"]["login"] == author)
    gaps = []
    for o in others:
        nxt = [a for a in agent_ts if a >= o]
        if nxt:
            gaps.append((nxt[0] - o).total_seconds() / 60)
    human_logins = [k for k in by_author if not BOT_RE.search(k)]

    S["case_b"] = {
        "repo": d["repo"], "number": pr["number"], "title": pr["title"], "author": author,
        "days": round((merged - created).total_seconds() / 86400, 1),
        "loc": pr["additions"] + pr["deletions"], "files": pr["changedFiles"],
        "commits": pr["commits"]["totalCount"],
        "n_reviews": pr["reviews"]["totalCount"],
        "review_states": sorted({r["state"] for r in revs}),
        "n_approved": sum(1 for r in revs if r["state"] == "APPROVED"),
        "n_changes_requested": sum(1 for r in revs if r["state"] == "CHANGES_REQUESTED"),
        "reviews_by_author": dict(sorted(by_author.items(), key=lambda kv: -kv[1])),
        "ai_reviewer_login": "copilot-pull-request-reviewer",
        "ai_reviewer_submissions": len(ai_rev),
        "ai_reviewer_malfunction": ai_malfunction,
        "ai_reviewer_substantive": len(ai_rev) - ai_malfunction,
        "n_threads": pr["reviewThreads"]["totalCount"],
        "threads_resolved": sum(1 for t in threads if t["isResolved"]),
        "threads_outdated": sum(1 for t in threads if t["isOutdated"]),
        "thread_openers": dict(sorted(openers.items(), key=lambda kv: -kv[1])),
        "n_revert_commits": len(revert_commits),
        "revert_commit_headlines": revert_commits,
        "agent_response_median_minutes": round(med(gaps), 1),
        "agent_response_p90_minutes": round(q(gaps, 0.9), 1),
        "agent_response_n": len(gaps),
        "human_reviewer_logins": sorted(human_logins),
        "n_issue_comments": len(issue_comments),
        "issue_comment_authors": sorted({c["author"]["login"] for c in issue_comments}),
    }


# ---------------------------------------------------------------- D7
def analyze_d7() -> None:
    data = load("d7_bot_review_text.json")
    if not data:
        S["d7_present"] = False
        return
    S["d7_present"] = True
    bot = [r for r in data if r["reviewer"] and BOT_RE.search(r["reviewer"])]
    bodies = [r for r in bot if (r["body"] or "").strip()]
    mal = [r for r in bodies if MALFUNCTION_RE.search(r["body"])]
    per: dict[str, dict] = {}
    for r in bodies:
        d = per.setdefault(r["reviewer"], {"reviewer": r["reviewer"], "bodies": 0,
                                           "malfunction": 0})
        d["bodies"] += 1
        if MALFUNCTION_RE.search(r["body"]):
            d["malfunction"] += 1
    rows = sorted(per.values(), key=lambda d: -d["bodies"])
    for d in rows:
        d["substantive_pct"] = pct(d["bodies"] - d["malfunction"], d["bodies"])
    write_table("t08_bot_review_signal.csv", rows,
                ["reviewer", "bodies", "malfunction", "substantive_pct"])
    S["d7_total_reviews"] = len(data)
    S["d7_bot_reviews"] = len(bot)
    S["d7_bot_bodies_nonempty"] = len(bodies)
    S["d7_malfunction"] = len(mal)
    S["d7_substantive_pct"] = pct(len(bodies) - len(mal), len(bodies))
    S["d7_malfunction_pct"] = pct(len(mal), len(bodies))
    S["d7_n_prs"] = len({(r["repo"], r["number"]) for r in data})
    S["d7_by_reviewer"] = {d["reviewer"]: d for d in rows}


# ---------------------------------------------------------------- 汇总对照
def build_comparison() -> None:
    """人类 PR 与 agent PR 的门禁强度对照表。"""
    if not S.get("d3_present"):
        return
    rows = [
        {"group": "人类作者 / 成熟仓库（D1）", "n": S["d1_n"],
         "median_review_submissions": S["d1_pooled_median_reviews"],
         "pct_zero_formal_review": S["d1_pooled_pct_zero_formal_review"],
         "pct_zero_review_and_comment": S["d1_pooled_pct_zero_review_and_comment"],
         "median_loc_changed": S["d1_pooled_median_loc"],
         "median_hours_to_merge": S["d1_pooled_median_hours"]},
        {"group": "agent 作者 / 全样本（D3）", "n": S["d3_n_merged_all"],
         "median_review_submissions": S["d3_pooled_all"]["median_review_submissions"],
         "pct_zero_formal_review": S["d3_pooled_all"]["pct_zero_formal_review"],
         "pct_zero_review_and_comment": S["d3_pooled_all"]["pct_zero_review_and_comment"],
         "median_loc_changed": S["d3_pooled_all"]["median_loc_changed"],
         "median_hours_to_merge": S["d3_pooled_all"]["median_hours_to_merge"]},
        {"group": f"agent 作者 / star≥{STAR_CUT}（D3）", "n": S["d3_n_mature"],
         "median_review_submissions": S["d3_pooled_mature"]["median_review_submissions"],
         "pct_zero_formal_review": S["d3_pooled_mature"]["pct_zero_formal_review"],
         "pct_zero_review_and_comment": S["d3_pooled_mature"]["pct_zero_review_and_comment"],
         "median_loc_changed": S["d3_pooled_mature"]["median_loc_changed"],
         "median_hours_to_merge": S["d3_pooled_mature"]["median_hours_to_merge"]},
        {"group": f"agent 作者 / star<{STAR_CUT}（D3）", "n": S["d3_n_small"],
         "median_review_submissions": S["d3_pooled_small"]["median_review_submissions"],
         "pct_zero_formal_review": S["d3_pooled_small"]["pct_zero_formal_review"],
         "pct_zero_review_and_comment": S["d3_pooled_small"]["pct_zero_review_and_comment"],
         "median_loc_changed": S["d3_pooled_small"]["median_loc_changed"],
         "median_hours_to_merge": S["d3_pooled_small"]["median_hours_to_merge"]},
    ]
    write_table("t09_gate_strength_comparison.csv", rows,
                ["group", "n", "median_review_submissions", "pct_zero_formal_review",
                 "pct_zero_review_and_comment", "median_loc_changed", "median_hours_to_merge"])
    # 跨组差异（百分点）。pct_zero_review_and_comment 是通道无关口径，是两组唯一可直接相减的量。
    S["gate_gap_zero_review_mature_pp"] = round(
        S["d3_pooled_mature"]["pct_zero_formal_review"]
        - S["d1_pooled_pct_zero_formal_review"], 2)
    S["gate_gap_zero_rc_mature_pp"] = round(
        S["d3_pooled_mature"]["pct_zero_review_and_comment"]
        - S["d1_pooled_pct_zero_review_and_comment"], 2)
    S["gate_gap_zero_rc_small_pp"] = round(
        S["d3_pooled_small"]["pct_zero_review_and_comment"]
        - S["d1_pooled_pct_zero_review_and_comment"], 2)


# ---------------------------------------------------------------- D9：被阻塞 PR 的去向
def analyze_d9() -> None:
    """一个 PR 一旦被正式阻塞，它后来怎么了。

    这是「循环没能收敛时会发生什么」的直接测量。三件事必须分开算：

      (a) 条件概率 P(未合并 | 曾被阻塞)。D1 与 D2 是两个独立抽样框（各取最近 100 个），
          直接相除会得到一个无意义的数；必须用总体基数加权。
      (b) 被阻塞且未合并的一侧：终结得干不干脆。关键对照量是「从未被阻塞的关闭 PR」的
          开放天数——若两者接近，说明阻塞被及时裁决；若差很多，说明阻塞导致的是烂掉。
      (c) 被阻塞但最终合并的一侧。只看死亡会得到「阻塞即死刑」的错误印象，必须同时看
          走出来的那批用了多久、靠什么走出来。
    """
    d9 = load("d9_blocked_fate.json")
    if not d9:
        S["d9_present"] = False
        return
    S["d9_present"] = True
    bc, bm = d9["blocked_closed"], d9["blocked_merged"]
    S["d9_n_blocked_closed"] = len(bc)
    S["d9_n_blocked_merged"] = len(bm)
    S["d9_base_since"] = d9["base_since"]

    # ---- (a) 条件概率
    d1, d2 = load("d1_merged_prs.json") or {}, load("d2_closed_prs.json") or {}
    rows = []
    for repo, b in d9["base"].items():
        if not b.get("reliable"):
            continue
        nm = sum(1 for p in d1.get(repo, []) if p.get("mergedAt") and cr_count(p) >= 1)
        nc = sum(1 for p in d2.get(repo, [])
                 if p.get("closedAt") and not p.get("mergedAt") and cr_count(p) >= 1)
        em = nm / 100 * b["merged_total"]
        ec = nc / 100 * b["closed_unmerged_total"]
        rows.append({
            "repo": repo,
            "pct_blocked_of_merged": pct(nm, 100),
            "pct_blocked_of_closed": pct(nc, 100),
            "merged_total": b["merged_total"],
            "closed_unmerged_total": b["closed_unmerged_total"],
            "pct_closed_given_blocked": round(100 * ec / (em + ec), 1) if em + ec else 0.0,
            "estimate_unstable": nm == 0,      # 分子为 0 时该估计不稳，正文须标注
        })
    write_table("t12_blocked_pr_fate_by_repo.csv", rows, list(rows[0]) if rows else [])
    S["d9_by_repo"] = {r["repo"]: r for r in rows}
    stable = [r for r in rows if not r["estimate_unstable"]]
    S["d9_pcgb_min"] = min(r["pct_closed_given_blocked"] for r in stable)
    S["d9_pcgb_max"] = max(r["pct_closed_given_blocked"] for r in stable)
    S["d9_pcgb_min_repo"] = min(stable, key=lambda r: r["pct_closed_given_blocked"])["repo"]
    S["d9_pcgb_max_repo"] = max(stable, key=lambda r: r["pct_closed_given_blocked"])["repo"]
    S["d9_n_repos_stable"] = len(stable)

    # ---- (b) 未合并的一侧
    # 时长一律取自 D2 快照里冻结的 closedAt，而非 D9 重取的当前值：至少有一个 PR 在基准日
    # 之后被重开，其 closedAt 变回 null，若用当前值会让分母从 38 静默降到 37。状态漂移
    # 单独计数上报，不允许它污染时长统计。
    frozen = {f"{r}#{p['number']}": p for r, prs in d2.items() for p in prs}
    days, drifted = [], 0
    for k, p in bc.items():
        f = frozen.get(k)
        if f and f.get("closedAt"):
            days.append((ts(f["closedAt"]) - ts(f["createdAt"])).total_seconds() / 86400)
        if not p.get("closedAt"):
            drifted += 1
    S["d9_closed_n_reopened_since_baseline"] = drifted
    S["d9_closed_n_with_duration"] = len(days)
    closes = [[n for n in p["timelineItems"]["nodes"] if n["__typename"] == "ClosedEvent"]
              for p in bc.values()]
    reopens = [sum(1 for n in p["timelineItems"]["nodes"] if n["__typename"] == "ReopenedEvent")
               for p in bc.values()]
    botclosed = sum(1 for cs in closes if any(
        BOT_RE.search(((c.get("actor") or {}).get("login") or "")) for c in cs))
    S["d9_closed_median_days"] = round(med(days), 1)
    S["d9_closed_p90_days"] = round(q(days, 0.9), 1)
    S["d9_closed_max_days"] = round(max(days), 1) if days else 0
    S["d9_closed_pct_over_90d"] = pct(sum(1 for d in days if d > 90), len(days))
    S["d9_closed_median_reviews"] = int(med([p["reviews"]["totalCount"] for p in bc.values()]))
    S["d9_closed_median_comments"] = int(med([p["comments"]["totalCount"] for p in bc.values()]))
    S["d9_closed_pct_bot_closed"] = pct(botclosed, len(bc))
    S["d9_closed_pct_oscillated"] = pct(sum(1 for r in reopens if r >= 1), len(reopens))
    S["d9_closed_max_close_events"] = max((len(c) for c in closes), default=0)
    # 对照组：同样关闭未合并、但从未被正式阻塞
    nb = [(ts(p["closedAt"]) - ts(p["createdAt"])).total_seconds() / 86400
          for prs in d2.values() for p in prs
          if p.get("closedAt") and not p.get("mergedAt") and cr_count(p) == 0]
    S["d9_unblocked_closed_n"] = len(nb)
    S["d9_unblocked_closed_median_days"] = round(med(nb), 1)
    S["d9_rot_ratio"] = round(med(days) / med(nb), 1) if med(nb) else 0.0

    # ---- (c) 合并的一侧：从首次阻塞到合并
    gaps, after, both = [], [], 0
    for p in bm.values():
        revs = sorted((r for r in p["reviews"]["nodes"] if r.get("submittedAt")),
                      key=lambda r: r["submittedAt"])
        crs = [r for r in revs if r["state"] == "CHANGES_REQUESTED"]
        if not crs:
            continue
        t0 = ts(crs[0]["submittedAt"])
        gaps.append((ts(p["mergedAt"]) - t0).total_seconds() / 86400)
        after.append(sum(1 for r in revs if ts(r["submittedAt"]) > t0))
        blockers = {r["author"]["login"] for r in crs if r["author"]}
        approvers = {r["author"]["login"] for r in revs
                     if r["state"] == "APPROVED" and r["author"]}
        both += bool(blockers & approvers)
    S["d9_merged_median_days_block_to_merge"] = round(med(gaps), 1)
    # 与另外两组同口径（创建 → 终态），使三者可以画在同一根轴上
    S["d9_merged_median_days_create_to_merge"] = round(med(
        [(ts(p["mergedAt"]) - ts(p["createdAt"])).total_seconds() / 86400
         for p in bm.values()]), 1)
    S["d9_merged_max_days_block_to_merge"] = round(max(gaps), 1) if gaps else 0
    S["d9_merged_median_reviews_after_block"] = int(med(after))
    S["d9_merged_pct_blocker_also_approved"] = pct(both, len(bm))

    # ---- 补丁死了，工作是否被接续（弱信号：交叉引用不等于取代）
    sup = sum(1 for p in bc.values() if any(
        n["__typename"] == "CrossReferencedEvent" and (n.get("source") or {}).get("merged")
        for n in p["timelineItems"]["nodes"]))
    S["d9_closed_n_xref_merged_pr"] = sup
    S["d9_closed_pct_xref_merged_pr"] = pct(sup, len(bc))
    S["d9_gaps"] = d9.get("gaps", [])


def corpus_size() -> None:
    """全部数据集去重后的不同 PR 数。

    抬头处的样本规模曾是手写数字且与实际不符（见 report.md §9.2 的 B9）。根因是它没有
    对应的可核对量，所以在此计算：按 (仓库, PR 号) 去重，因为 D7 完全包含于 D3、D8 与 D1
    指向同一批 PR、两个案例 PR 亦分别落在 D1 与 D3 内。
    """
    d1 = load("d1_merged_prs.json") or {}
    d2 = load("d2_closed_prs.json") or {}
    d3 = load("d3_agent_prs.json") or {}
    d5 = load("d5_cases.json") or {}
    d7 = load("d7_bot_review_text.json") or []
    s1 = {(r, p["number"]) for r, v in d1.items() for p in v}
    s2 = {(r, p["number"]) for r, v in d2.items() for p in v}
    s3 = {(p["repository"]["nameWithOwner"], p["number"])
          for b in d3.values() for k in ("merged", "closed_unmerged") for p in b[k]}
    s5 = {(v["repo"], v["pr"]["number"]) for v in d5.values()}
    s7 = {(r["repo"], r["number"]) for r in d7}
    S["corpus_distinct_prs"] = len(s1 | s2 | s3 | s5 | s7)
    S["corpus_by_dataset"] = {"d1": len(s1), "d2": len(s2), "d3": len(s3),
                              "d5": len(s5), "d7": len(s7)}
    S["corpus_d7_subset_of_d3"] = not (s7 - s3)


def main() -> None:
    analyze_d1()
    analyze_offchannel()
    analyze_d2()
    analyze_d3()
    analyze_cluster_sensitivity()
    analyze_d4()
    analyze_case_a()
    analyze_case_b()
    analyze_d7()
    analyze_d9()
    build_comparison()
    corpus_size()
    man = load("manifest.json") or {}
    S["baseline_date"] = man.get("baseline_date", "")
    S["api_calls"] = len(man.get("calls", []))
    S["collection_gaps"] = man.get("gaps", [])
    (DER / "stats.json").write_text(json.dumps(S, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"derived/stats.json：{len(S)} 个顶层键")
    print(f"derived/tables/：{len(list(TAB.glob('*.csv')))} 张表")
    for k in ("d1_n", "d2_n", "d3_n_merged_all", "d3_n_mature", "d4_pooled_pct",
              "d7_substantive_pct"):
        print(f"  {k} = {S.get(k)}")


if __name__ == "__main__":
    main()
