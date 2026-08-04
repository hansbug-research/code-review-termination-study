#!/usr/bin/env python3
"""对 report.md 与 README.md 的每一条事实性主张做机器核对。

设计意图。本仓库主张「正文里的每个数字都可以被追溯到落盘数据」。这个主张本身必须是
可执行的，否则它只是一句自我表扬。本脚本把它变成一个通过/失败的判定：每条断言由
derived/stats.json（或落盘的 CSV / 文件系统）算出一个字符串，再要求该字符串**逐字出现**
在正文中。任何一条不匹配即退出码非 0。

这同时构成本仓库自身评审流程的 L1 verifier（见 report.md §8.1、§9）：verifier 全绿是进入
评审的前置条件，而不是评审之后的补充检查。

用法：
    python3 scripts/verify.py            # 全量核对，失败时退出码 1
    python3 scripts/verify.py --list     # 只列出全部断言及其期望值
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = json.loads((ROOT / "derived" / "stats.json").read_text())
REPORT = (ROOT / "report.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""
CORPUS = REPORT + "\n" + README

CHECKS: list[tuple[str, str, bool]] = []      # (标签, 期望出现的字符串, 是否通过)
NOTES: list[str] = []


def a(label: str, needle: str, corpus: str = CORPUS) -> None:
    """断言 needle 逐字出现在正文中。"""
    CHECKS.append((label, needle, needle in corpus))


def num(x: float) -> str:
    """整数去掉小数尾；否则保留原样（与正文写法一致）。"""
    return str(int(x)) if float(x) == int(x) else str(x)


def thousands(n: int) -> str:
    return f"{n:,}"


# ---------------------------------------------------------------- 基准与规模
a("基准日", S["baseline_date"])
a("语料规模（抬头）", f'一手数据 **{thousands(S["corpus_distinct_prs"])} 个不同 PR')
a("语料规模（§9.2 证据）",
  f'D1 {S["corpus_by_dataset"]["d1"]} + D2 {S["corpus_by_dataset"]["d2"]} '
  f'+ D3 {thousands(S["corpus_by_dataset"]["d3"])} + 案例 {S["corpus_by_dataset"]["d5"]}')
CHECKS.append(("D7 完全包含于 D3", "corpus_d7_subset_of_d3", bool(S["corpus_d7_subset_of_d3"])))
a("API 调用次数", f'{S["api_calls"]} 次 GraphQL 调用')
a("采集缺口数", f'共记录 **{len(S["collection_gaps"])} 处缺口**')

# ---------------------------------------------------------------- D1
a("D1 样本量", f'D1 的 {thousands(S["d1_n"])} 个已合并 PR')
a("D1 零阻塞态占比", f'**{S["d1_pooled_pct_zero_cr"]}%**')
a("D1 ≥1 阻塞态占比", f'| ≥1 次 `CHANGES_REQUESTED` | {S["d1_pooled_pct_ge1_cr"]}% |')
a("D1 最大阻塞次数", f'| **{S["d1_pooled_max_cr"]}** |')
a("D1 review 提交中位", f'| review 提交数（中位） | **{S["d1_pooled_median_reviews"]}** |')
a("D1 改动中位", f'| 改动行数（中位） | {S["d1_pooled_median_loc"]} |')
a("D1 合并耗时中位", f'| 创建到合并耗时（中位） | {S["d1_pooled_median_hours"]} h |')
a("D1 批准中位", f'| `APPROVED` 次数（中位） | {S["d1_pooled_median_approvals"]} |')
a("D1 零批准占比", f'| 零 `APPROVED` 合并 | {S["d1_pooled_pct_zero_approval"]}% |')
a("D1 零 CR 区间下限", f'{S["d1_min_pct_zero_cr"]}%（rust）')
a("D1 零 CR 区间上限", f'{S["d1_max_pct_zero_cr"]}%（cpython）')
a("D1 零正式 review 率", f'**{S["d1_pooled_pct_zero_formal_review"]}%**')
a("D1 严格零关注率", f'**{S["d1_pooled_pct_zero_review_and_comment"]}%**')
for repo, key in (("rust-lang/rust", "rust"), ("kubernetes/kubernetes", "k8s"),
                  ("nodejs/node", "node"), ("pytorch/pytorch", "pytorch"),
                  ("python/cpython", "cpython")):
    d = S["d1_by_repo"][repo]
    a(f"D1 {key} 合并耗时中位出现", num(d["median_hours_to_merge"]))

# ---------------------------------------------------------------- D2
a("D2 样本量", f'D2 的 {thousands(S["d2_n"])} 个关闭未合并 PR')
a("D2 开放天数中位", f'| 开放天数（中位） | **{S["d2_pooled_median_days"]}** |')
a("D2 开放天数 p90", f'| 开放天数（p90） | **{S["d2_pooled_p90_days"]}** |')
a("D2 开放天数最大", f'| 开放天数（最大） | {thousands(S["d2_pooled_max_days"])} |')
a("D2 从未 review 占比", f'| 从未被 review 过 | **{S["d2_pooled_pct_never_reviewed"]}%** |')
a("D2 ≥1 CR 占比", f'{S["d2_pooled_pct_ge1_cr"]}%')
a("D2 stale 占比", f'{S["d2_pooled_pct_stale_labeled"]}%')
a("D2 最高 stale 仓库", f'kubernetes 最高，{S["d2_max_stale_pct"]}%')
a("D2 k8s 开放天数中位", f'kubernetes 则是 {S["d2_by_repo"]["kubernetes/kubernetes"]["median_days_open"]} 天')
a("D2 rust 开放天数中位", f'rust 的中位仅 {S["d2_by_repo"]["rust-lang/rust"]["median_days_open"]} 天')

# ---------------------------------------------------------------- D3
a("D3 已合并总量", f'**{thousands(S["d3_n_merged_all"])} 个已合并 PR**')
a("D3 仓库数", f'**{S["d3_n_repos"]} 个仓库**')
a("D3 成熟层占比", f'**{S["d3_n_mature"]} 个（{S["d3_pct_in_mature_repos"]}%）**')
a("D3 成熟层仓库数", f'涉及 {S["d3_mature_n_repos"]} 个仓库')
a("D3 star 阈值", f'star ≥ {S["d3_star_cut"]}')
for stratum, key in (("全样本", "d3_pooled_all"), ("成熟层", "d3_pooled_mature"),
                     ("小仓库层", "d3_pooled_small")):
    d = S[key]
    a(f"D3 {stratum} n", thousands(d["n"]))
    a(f"D3 {stratum} 零正式 review", f'{d["pct_zero_formal_review"]}%')
    a(f"D3 {stratum} 严格零关注", f'{d["pct_zero_review_and_comment"]}%')
a("D3 全样本合并耗时中位", f'{S["d3_pooled_all"]["median_minutes_to_merge"]} min')
a("D3 成熟层合并耗时中位", f'{S["d3_pooled_mature"]["median_minutes_to_merge"]} min')
a("D3 小仓库层合并耗时中位", f'{S["d3_pooled_small"]["median_minutes_to_merge"]} min')
a("D3 全样本 10 分钟内合并", f'{S["d3_pooled_all"]["pct_merged_under_10min"]}%')
a("jules 无成熟仓库样本", "无一**落在成熟仓库")

# ---------------------------------------------------------------- D3 聚簇
a("成熟层主导仓库", S["d3_mature_top_repo"])
a("成熟层严格零关注总数", f'**{S["d3_mature_strict_zero_n"]} 个「零 review 且零评论」')
a("成熟层主导仓库命中数", f'{S["d3_mature_strict_zero_top_repo_n"]} 个（{S["d3_mature_strict_zero_share_in_top_repo_pct"]}%）')
a("成熟层主导仓库占比", f'{S["d3_mature_top_repo_share_pct"]}% 的 PR')
a("成熟层刀切下限", f'**{S["d3_mature_loo_min_pct"]}%')
a("成熟层刀切上限", f'{S["d3_mature_loo_max_pct"]}%**')
a("成熟层宏平均", f'{S["d3_mature_macro_avg_strict_zero_pct"]}%')
a("成熟层有命中的仓库数", f'只有 **{S["d3_mature_n_repos_with_any_strict_zero"]} 个**')
a("小仓库层仓库数", f'{S["d3_small_n_repos"]} 个仓库')
a("小仓库层刀切下限", f'**{S["d3_small_loo_min_pct"]}%')
a("小仓库层刀切上限", f'{S["d3_small_loo_max_pct"]}%**')
a("小仓库层宏平均", f'{S["d3_small_macro_avg_strict_zero_pct"]}%')
a("小仓库层最大仓库占比", f'{S["d3_small_top_repo_share_pct"]}%')

# ---------------------------------------------------------------- D4
a("D4 分母", thousands(S["d4_merged_total"]))
a("D4 分子", f'| **{S["d4_revert_total"]}** |')
a("D4 合并比例", f'**{S["d4_pooled_pct"]}%**')
a("D4 起始日", S["d4_since"])
for repo in S["d4_by_repo"]:
    d = S["d4_by_repo"][repo]
    a(f"D4 {repo} 比例", f'**{d["revert_pct"]}%**')
    a(f"D4 {repo} 分母", thousands(d["merged_total"]))

# ---------------------------------------------------------------- D7
a("D7 PR 数", f'{S["d7_n_prs"]} 个成熟仓库 agent PR')
a("D7 review 总数", f'共 {S["d7_total_reviews"]} 条 review 记录')
a("D7 机器人 review 数", f'机器人 review {S["d7_bot_reviews"]} 条')
a("D7 非空正文数", f'正文非空 {S["d7_bot_bodies_nonempty"]} 条')
a("D7 机械失败占比", f'{S["d7_malfunction"]}（{S["d7_malfunction_pct"]}%）')
a("D7 实质内容占比", f'**{S["d7_substantive_pct"]}%**')
a("D7 copilot reviewer 占比",
  f'| `copilot-pull-request-reviewer` | {S["d7_by_reviewer"]["copilot-pull-request-reviewer"]["bodies"]} '
  f'| {S["d7_by_reviewer"]["copilot-pull-request-reviewer"]["malfunction"]} '
  f'| **{S["d7_by_reviewer"]["copilot-pull-request-reviewer"]["substantive_pct"]}%** |')

# ---------------------------------------------------------------- D8 旁路批准
a("D8 零 review 总数", f'共有 **{S["d8_n_zero_formal_review"]} 个已合并 PR**')
a("D8 旁路批准数", f'**{S["d8_n_offchannel_approved"]} 个（{S["d8_pct_offchannel_of_zero"]}%）可归因于旁路批准**')
a("D8 未识别数", f'剩余 {S["d8_n_unattributed"]} 个（占 D1 全样本 {S["d8_pooled_pct_unattributed"]}%）')
a("D8 k8s lgtm 命中", f'kubernetes 的 {S["d8_k8s_lgtm_of_zero"]} 个零 review PR **全部命中**'
                      f'（{S["d8_k8s_lgtm_of_zero"]}/{S["d8_k8s_lgtm_of_zero"]}）')
a("D8 cpython backport 命中", f'cpython 54 个零 review PR 中 {S["d8_cpython_missislington_of_zero"]} 个')

# ---------------------------------------------------------------- 案例 A
CA = S["case_a"]
a("案例 A 标识", f'{CA["repo"]}#{CA["number"]}')
a("案例 A 三元组", f'{CA["days"]} 天 / {thousands(CA["loc"])} 行 / {CA["files"]} 个文件')
a("案例 A review 数", f'**{CA["n_reviews"]} 次**')
a("案例 A COMMENTED", f'`COMMENTED` {CA["review_states"]["COMMENTED"]}')
a("案例 A APPROVED", f'**`APPROVED` {CA["n_approved"]}**')
a("案例 A CHANGES_REQUESTED", f'`CHANGES_REQUESTED` **{CA["n_changes_requested"]}**')
a("案例 A 参与者", f'{CA["n_participants"]} 人')
a("案例 A 自评次数", f'作者本人自评 {CA["author_self_reviews"]} 次')
a("案例 A 标签事件", f'{CA["n_label_events"]} 个')
a("案例 A 状态事件", f'`S-*` 状态事件 {CA["n_state_label_events"]} 个')
a("案例 A 状态种类", f'涉及 {CA["n_distinct_state_labels"]} 个不同状态')
a("案例 A 并发状态时长", f'**{CA["multi_state_days"]} 天（{CA["pct_time_multi_state"]}%）同时挂着 ≥2 个 `S-*` 标签**')

# ---------------------------------------------------------------- 案例 B
CB = S["case_b"]
a("案例 B 标识", f'{CB["repo"]}#{CB["number"]}')
a("案例 B 四元组", f'{CB["days"]} 天 / {CB["loc"]} 行 / {CB["files"]} 个文件 / **{CB["commits"]} 个 commit**')
a("案例 B review 数", f'**{CB["n_reviews"]} 次**')
a("案例 B APPROVED", f'`APPROVED` {CB["n_approved"]}')
a("案例 B CHANGES_REQUESTED", f'`CHANGES_REQUESTED` **{CB["n_changes_requested"]}**')
a("案例 B 作者分解", f'`jkotas` {CB["reviews_by_author"]["jkotas"]}、'
                     f'`copilot-swe-agent` {CB["reviews_by_author"]["copilot-swe-agent"]}、'
                     f'`copilot-pull-request-reviewer` {CB["reviews_by_author"]["copilot-pull-request-reviewer"]}、'
                     f'`janvorli` {CB["reviews_by_author"]["janvorli"]}')
a("案例 B thread 数", f'{CB["n_threads"]} 条，**全部 {CB["threads_resolved"]} 条由 `jkotas` 一人开启**')
a("案例 B outdated", f'{CB["threads_outdated"]} 条 outdated')
a("案例 B 回退 commit", f'| **{CB["n_revert_commits"]} 个** |')
a("案例 B 响应中位", f'中位 **{CB["agent_response_median_minutes"]} 分钟**')
a("案例 B 响应 p90", f'p90 {CB["agent_response_p90_minutes"]} 分钟（n={CB["agent_response_n"]}）')
a("案例 B AI reviewer 提交", f'{CB["ai_reviewer_submissions"]} 次提交中，**{CB["ai_reviewer_malfunction"]} 次为机械失败模板**')
a("案例 B AI reviewer 实质", f'实质内容 {CB["ai_reviewer_substantive"]} 次')
for h in CB["revert_commit_headlines"]:
    a(f"案例 B 回退标题：{h[:28]}", h)

# ---------------------------------------------------------------- 自审日志
LOG = list(csv.DictReader((ROOT / "audit" / "self_review_log.csv").open(encoding="utf-8")))
BS = [int(r["blocking_open"]) for r in LOG]
a("自审曲线", " → ".join(str(b) for b in BS))
for i, b in enumerate(BS):
    a(f"自审第 {i+1} 轮 |B|", f'$|B_{i}| = {b}$')
CHECKS.append(("自审曲线严格递减", "B_n 严格递减",
               all(x > y for x, y in zip(BS, BS[1:]))))
CHECKS.append(("自审终止于 0", "|B_final| == 0", BS[-1] == 0))

# ---------------------------------------------------------------- 结构性核对
FIGS = sorted((ROOT / "figures").glob("*.png"))
TABS = sorted((ROOT / "derived" / "tables").glob("*.csv"))
CHECKS.append(("图数量与抬头一致", f'图 **{len(FIGS)} 张**',
               f'图 **{len(FIGS)} 张**' in CORPUS))
CHECKS.append(("表数量与抬头一致", f'可复算表 **{len(TABS)} 张**',
               f'可复算表 **{len(TABS)} 张**' in CORPUS))
for f in FIGS:
    CHECKS.append((f"图被引用：{f.name}", f.name, f.name in CORPUS))
for t in TABS:
    CHECKS.append((f"表被引用：{t.name}", t.stem.split("_")[0],
                   t.name in CORPUS or t.stem.split("_")[0] in CORPUS))
for ref in re.findall(r"!\[[^\]]*\]\((figures/[^)]+)\)", CORPUS):
    CHECKS.append((f"图片路径存在：{ref}", ref, (ROOT / ref).exists()))

# 引文档案中登记的撤销条目数，必须与正文声明一致
QUOTES = (ROOT / "lit" / "quotes.md").read_text(encoding="utf-8")
n_revoked = len(re.findall(r"^### 9\.\d+ ", QUOTES, re.M))
a("撤销引用数", f'**{n_revoked} 条引用因未能在原文定位而撤销**')
a("撤销引用数（正文）", f'**撤销了 {n_revoked} 条引用**')

# 文献清单条数
LITROWS = list(csv.DictReader((ROOT / "lit" / "manifest.csv").open(encoding="utf-8")))
a("文献篇数", f'全文核对文献 **{len(LITROWS)} 篇**')
a("文献篇数（方法节）", f'下载 {len(LITROWS)} 篇论文全文')

# stats.json 键数
a("stats 键数", f'`derived/stats.json`（{len(S)} 个键）')

# 断言总数自洽：正文声明的条数必须等于本脚本实际执行的条数
DECLARED = re.search(r"机器核对断言 \*\*(\d+) 条\*\*", CORPUS)


def main() -> int:
    if "--list" in sys.argv:
        for label, needle, _ in CHECKS:
            print(f"{label}\t{needle}")
        return 0
    failed = [(l, n) for l, n, ok in CHECKS if not ok]
    total = len(CHECKS) + 1                      # +1 为断言计数自洽这一条
    declared_ok = bool(DECLARED) and int(DECLARED.group(1)) == total
    for label, needle in failed:
        print(f"FAIL  {label}\n      期望出现：{needle!r}")
    if not declared_ok:
        got = DECLARED.group(1) if DECLARED else "缺失"
        print(f"FAIL  断言计数自洽\n      正文声明 {got} 条，实际执行 {total} 条")
    ok = total - len(failed) - (0 if declared_ok else 1)
    print(f"\n{ok}/{total} 条断言通过")
    for n in NOTES:
        print(f"  note: {n}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
