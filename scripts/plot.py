#!/usr/bin/env python3
"""从 derived/stats.json 与 derived/tables/*.csv 出图，写入 figures/。

配色、标记与图表形式遵循一套统一规范：分类色按固定槽位顺序取用（从不循环生成）、
顺序量用单色由浅到深、绝不使用双 y 轴、细标记 + 实线发丝网格、图例在系列数 ≥2 时必备
并对关键系列直接标注数值。所选调色板已由校验器在「相邻对」与「全对」两种配对表下
分别通过全部硬门槛，产物见 audit/palette_validation.md。

用法：
    python3 scripts/plot.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parent.parent
DER = ROOT / "derived"
TAB = DER / "tables"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

# ---- 设计令牌（浅色画布一套；PNG 在深色页面上作为浅色卡片呈现）----
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"
# 分类槽位，固定顺序，不循环
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
# 顺序色阶（单一蓝色由浅到深）。用于有序分箱时，最浅一档不浅于 step 250，保证 ≥2:1
SEQ = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
STATUS_CRIT = "#d03b3b"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Noto Sans CJK SC", "Noto Sans CJK JP", "Droid Sans Fallback",
                        "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": BASE,
    "axes.labelcolor": INK2,
    "axes.titlecolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": INK2,
    "ytick.labelcolor": INK2,
    "grid.color": GRID,
    "grid.linewidth": 0.7,
    "grid.linestyle": "-",          # 发丝实线；虚线网格是反模式
    "axes.grid": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "figure.dpi": 160,
    "savefig.dpi": 160,
    "savefig.bbox": "tight",
    "font.size": 10.5,
})

S = json.loads((DER / "stats.json").read_text())


def table(name: str) -> list[dict]:
    p = TAB / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def short(repo: str) -> str:
    return repo.split("/")[-1]


def finish(ax, xlabel: str = "", ylabel: str = "", xgrid: bool = False,
           ygrid: bool = False) -> None:
    if xgrid:
        ax.xaxis.grid(True)
    if ygrid:
        ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9.5)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9.5)
    ax.tick_params(length=0)


def save(fig, name: str) -> None:
    fig.savefig(FIG / name)
    plt.close(fig)
    print(f"  {name}")


def rbar(ax, y, width, color, height=0.42, label=None):
    """圆头横条：用带圆帽的粗线段实现，数据端为圆角且锚定在基线上。"""
    lw = height * 72 / 2.54 * 0.9
    ax.plot([0, width], [y, y], color=color, linewidth=lw,
            solid_capstyle="round", label=label, zorder=3)


# ---------------------------------------------------------------- fig01
def fig01_changes_requested() -> None:
    """D1：已合并 PR 的正式阻塞态（CHANGES_REQUESTED）次数分布。有序三分箱 → 顺序色阶。"""
    rows = table("t01_merged_pr_review_structure.csv")
    if not rows:
        return
    rows = sorted(rows, key=lambda r: float(r["pct_zero_changes_requested"]))
    labels = [short(r["repo"]) for r in rows]
    zero = [float(r["pct_zero_changes_requested"]) for r in rows]
    one = [float(r["pct_ge1_changes_requested"]) - float(r["pct_ge2_changes_requested"])
           for r in rows]
    two = [float(r["pct_ge2_changes_requested"]) for r in rows]
    fig, ax = plt.subplots(figsize=(8.6, 3.5))
    y = range(len(rows))
    gap = 0.35   # 相邻填充之间留出画布色间隙，而不是描边
    left = [0.0] * len(rows)
    for vals, color, name in ((zero, SEQ[0], "0 次"), (one, SEQ[1], "1 次"),
                              (two, SEQ[2], "≥2 次")):
        ax.barh(list(y), vals, left=left, height=0.5, color=color, label=name,
                linewidth=0, zorder=3)
        left = [a + b + gap for a, b in zip(left, vals)]
    for i, v in enumerate(zero):
        ax.text(v / 2, i, f"{v:.0f}%", ha="center", va="center", color="#0b0b0b",
                fontsize=9.5, zorder=4)
    for i, (o, t) in enumerate(zip(one, two)):
        if o + t > 0:
            ax.text(100 + 1.5, i, f"{o + t:.0f}%", ha="left", va="center", color=INK2,
                    fontsize=9)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 108)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_title("已合并 PR 中「正式请求变更」的出现次数占比", fontsize=12, pad=12,
                 loc="left")
    ax.legend(loc="lower right", ncol=3, fontsize=9, bbox_to_anchor=(1.0, -0.28))
    finish(ax, xlabel="占该仓库最近 100 个已合并 PR 的比例（右侧数字为 ≥1 次的合计）",
           xgrid=True)
    save(fig, "fig01_changes_requested_distribution.png")


# ---------------------------------------------------------------- fig02
def fig02_review_submissions() -> None:
    """D1：review 提交数的中位 / p90 / 最大值。三个有序统计量 → 前三槽（全对已校验）。"""
    rows = table("t01_merged_pr_review_structure.csv")
    if not rows:
        return
    rows = sorted(rows, key=lambda r: int(r["median_review_submissions"]))
    labels = [short(r["repo"]) for r in rows]
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    y = list(range(len(rows)))
    series = [("中位数", "median_review_submissions", C[0]),
              ("p90", "p90_review_submissions", C[1]),
              ("最大值", "max_review_submissions", C[2])]
    for name, key, color in series:
        vals = [int(r[key]) for r in rows]
        ax.scatter(vals, y, s=70, color=color, label=name, zorder=3,
                   edgecolors=SURFACE, linewidths=2)   # 2px 画布色圆环，用于重叠标记
    for i, r in enumerate(rows):
        ax.plot([int(r["median_review_submissions"]), int(r["max_review_submissions"])],
                [i, i], color=GRID, linewidth=1.4, zorder=1)
        ax.text(int(r["max_review_submissions"]) + 1.5, i,
                str(r["max_review_submissions"]), va="center", color=INK2, fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, max(int(r["max_review_submissions"]) for r in rows) * 1.14)
    ax.set_title("同一批 PR 的 review 提交数：中位数很小，尾部很长", fontsize=12,
                 pad=12, loc="left")
    ax.legend(loc="lower right", ncol=3, fontsize=9)
    finish(ax, xlabel="单个 PR 上的 review 提交次数（含 COMMENTED，非仅阻塞态）",
           xgrid=True)
    save(fig, "fig02_review_submission_spread.png")


# ---------------------------------------------------------------- fig03
def fig03_closed_prs() -> None:
    """D2：关闭未合并 PR 的两个不同量纲指标 → 小多图，绝不共用双 y 轴。"""
    rows = table("t02_closed_unmerged_pr_structure.csv")
    if not rows:
        return
    rows = sorted(rows, key=lambda r: float(r["median_days_open"]))
    labels = [short(r["repo"]) for r in rows]
    y = list(range(len(rows)))
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.3))
    ax = axes[0]
    for i, r in enumerate(rows):
        rbar(ax, i, float(r["median_days_open"]), C[0])
        ax.text(float(r["median_days_open"]) + max(1, float(rows[-1]["median_days_open"]) * .03),
                i, f'{float(r["median_days_open"]):.0f}', va="center", color=INK2,
                fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_title("关闭前的开放天数（中位）", fontsize=11, pad=10, loc="left")
    finish(ax, xlabel="天", xgrid=True)
    ax = axes[1]
    for i, r in enumerate(rows):
        v = float(r["pct_stale_or_lifecycle_labeled"])
        rbar(ax, i, v, C[1] if v > 0 else GRID)
        ax.text(v + 2, i, f"{v:.0f}%", va="center", color=INK2, fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels(["" for _ in y])
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_title("带 stale / lifecycle 类标签的比例", fontsize=11, pad=10, loc="left")
    finish(ax, xlabel="占该仓库最近 100 个「关闭且未合并」PR 的比例", xgrid=True)
    fig.suptitle("未收敛的 PR 是怎么结束的：超时与放弃", fontsize=12.5, x=0.045,
                 ha="left", y=1.06)
    save(fig, "fig03_closed_unmerged_termination.png")


# ---------------------------------------------------------------- fig04
def fig04_gate_strength() -> None:
    """D1 vs D3：门禁强度对照，两个口径并列。

    两个系列同为百分比、同一 x 轴，故可并列而无需双轴。宽口径（零正式 review）高估门禁
    缺失，严格口径（零 review 且零 issue comment）低估之，二者构成区间估计。
    """
    rows = table("t09_gate_strength_comparison.csv")
    if not rows:
        return
    labels = [r["group"] for r in rows]
    ns = [r["n"] for r in rows]
    wide = [float(r["pct_zero_formal_review"]) for r in rows]
    strict = [float(r["pct_zero_review_and_comment"]) for r in rows]
    fig, ax = plt.subplots(figsize=(9.4, 3.9))
    h = 0.34
    for k, (vals, color, name) in enumerate((
            (wide, BASE, "零正式 review（宽口径，含旁路批准）"),
            (strict, C[0], "零 review 且零 issue comment（严格口径）"))):
        ys = [i + (k - 0.5) * (h + 0.04) for i in range(len(rows))]
        ax.barh(ys, vals, height=h, color=color, label=name, linewidth=0, zorder=3)
        for yy, vv in zip(ys, vals):
            ax.text(vv + 1.2, yy, f"{vv:.1f}%", va="center", color=INK2, fontsize=9)
    ax.set_yticks(list(range(len(rows))))
    ax.set_yticklabels([f"{l}\nn={n}" for l, n in zip(labels, ns)], fontsize=9.2)
    ax.set_xlim(0, 88)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.invert_yaxis()
    ax.set_title("门禁缺失率的两个口径：宽口径高估、严格口径低估，真值落在二者之间",
                 fontsize=12, pad=30, loc="left")
    ax.legend(loc="upper right", bbox_to_anchor=(1.0, 1.13), ncol=2, fontsize=8.8)
    finish(ax, xlabel="已合并 PR 中的占比", xgrid=True)
    save(fig, "fig04_gate_strength_by_repo_maturity.png")


# ---------------------------------------------------------------- fig14
def fig14_offchannel() -> None:
    """D8×D1：把「零正式 review」拆成旁路批准与无可见门禁两类。"""
    rows = table("t10_offchannel_approval_decomposition.csv")
    if not rows:
        return
    rows = sorted(rows, key=lambda r: -int(r["n_zero_formal_review"]))
    fig, ax = plt.subplots(figsize=(9.0, 3.4))
    ys = list(range(len(rows)))
    off = [int(r["n_offchannel_approved"]) for r in rows]
    sil = [int(r["n_unattributed"]) for r in rows]
    ax.barh(ys, off, height=0.5, color=C[2], label="旁路批准（lgtm / rollup / 自动 backport）",
            linewidth=0, zorder=3)
    ax.barh(ys, sil, height=0.5, left=off, color=STATUS_CRIT, label="未识别到批准痕迹",
            linewidth=0, zorder=3, edgecolor=SURFACE)
    for y, a, b in zip(ys, off, sil):
        if a:
            ax.text(a / 2, y, str(a), va="center", ha="center", color="#ffffff", fontsize=9)
        if b:
            ax.text(a + b + 1.0, y, str(b), va="center", color=INK2, fontsize=9)
    ax.set_yticks(ys)
    ax.set_yticklabels([short(r["repo"]) for r in rows], fontsize=9.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 66)
    ax.set_title("「零正式 review」并不等于「无人过目」：100/143 实为旁路批准",
                 fontsize=12, pad=12, loc="left")
    ax.legend(loc="lower right", fontsize=8.8)
    finish(ax, xlabel="已合并 PR 数（每仓库 n=100）", xgrid=True)
    save(fig, "fig14_offchannel_approval_decomposition.png")


# ---------------------------------------------------------------- fig15
def fig15_cluster_sensitivity() -> None:
    """D3 成熟层的仓库级聚簇：按 PR 计数的比率被单一仓库主导。"""
    rows = table("t11_mature_stratum_repo_clustering.csv")
    if not rows:
        return
    rows = sorted(rows, key=lambda r: (-int(r["n_zero_review_and_comment"]), -int(r["n"])))
    show = [r for r in rows if int(r["n"]) >= 2 or int(r["n_zero_review_and_comment"]) > 0]
    fig, ax = plt.subplots(figsize=(9.2, 4.0))
    ys = list(range(len(show)))
    tot = [int(r["n"]) for r in show]
    zer = [int(r["n_zero_review_and_comment"]) for r in show]
    ax.barh(ys, tot, height=0.5, color=BASE, label="该仓库的 agent PR 总数", linewidth=0,
            zorder=2)
    ax.barh(ys, zer, height=0.5, color=STATUS_CRIT, label="其中零 review 且零 comment",
            linewidth=0, zorder=3)
    for y, t, z in zip(ys, tot, zer):
        ax.text(t + 0.4, y, f"{z}/{t}", va="center", color=INK2, fontsize=8.8)
    ax.set_yticks(ys)
    ax.set_yticklabels([short(r["repo"]) for r in show], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 26)
    ax.set_title(f'成熟层 {S.get("d3_mature_strict_zero_n")} 个「零关注」PR 中 '
                 f'{S.get("d3_mature_strict_zero_top_repo_n")} 个来自同一仓库',
                 fontsize=12, pad=12, loc="left")
    ax.legend(loc="lower right", fontsize=8.8)
    finish(ax, xlabel="PR 数", xgrid=True)
    save(fig, "fig15_mature_stratum_clustering.png")


# ---------------------------------------------------------------- fig05
def fig05_agent_two_worlds() -> None:
    """D3：agent PR 的零正式 review 比例，按仓库成熟度分层。2 系列 → 前两槽 + 图例。"""
    rows = [r for r in table("t03_agent_pr_by_agent_and_stratum.csv")]
    if not rows:
        return
    cut = S.get("d3_star_cut", 500)
    apps = sorted({r["agent_app"] for r in rows})
    fig, ax = plt.subplots(figsize=(9.0, 3.6))
    h = 0.34
    for k, (stratum, color, name) in enumerate((
            (f"stars_lt{cut}", C[1], f"star < {cut}"),
            (f"stars_ge{cut}", C[0], f"star ≥ {cut}"))):
        ys, vs, labs = [], [], []
        for i, app in enumerate(apps):
            m = [r for r in rows if r["agent_app"] == app and r["stratum"] == stratum]
            if not m:
                continue
            ys.append(i + (k - 0.5) * (h + 0.04))
            vs.append(float(m[0]["pct_zero_formal_review"]))
            labs.append(m[0]["n"])
        ax.barh(ys, vs, height=h, color=color, label=name, linewidth=0, zorder=3)
        for yy, vv, nn in zip(ys, vs, labs):
            ax.text(vv + 1.5, yy, f"{vv:.0f}%  (n={nn})", va="center", color=INK2,
                    fontsize=8.8)
    ax.set_yticks(list(range(len(apps))))
    ax.set_yticklabels(apps, fontsize=9.5)
    ax.set_xlim(0, 118)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%" if v <= 100 else ""))
    ax.invert_yaxis()
    ax.set_title("同一个 agent 的 PR，零 review 合并率在成熟仓库里系统性下降（但未归零）",
                 fontsize=12, pad=30, loc="left")
    ax.legend(loc="upper right", bbox_to_anchor=(1.0, 1.12), ncol=2, fontsize=9)
    finish(ax, xlabel="已合并 PR 中「零正式 review 提交」的比例", xgrid=True)
    save(fig, "fig05_agent_pr_zero_review_by_stratum.png")


# ---------------------------------------------------------------- fig06
def fig06_agent_latency() -> None:
    """D3：agent PR 从创建到合并的耗时，两层对照。单轴、对数刻度。"""
    if not S.get("d3_present"):
        return
    cut = S.get("d3_star_cut", 500)
    pairs = [(f"star < {cut}", S["d3_pooled_small"], C[1]),
             (f"star ≥ {cut}", S["d3_pooled_mature"], C[0])]
    fig, ax = plt.subplots(figsize=(8.6, 2.9))
    for i, (name, d, color) in enumerate(pairs):
        v = max(d["median_minutes_to_merge"], 0.5)
        rbar(ax, i, v, color)
        hrs = d["median_hours_to_merge"]
        ax.text(v * 1.16, i, f"{v:,.0f} 分钟（≈{hrs:.0f} 小时）  n={d['n']}",
                va="center", color=INK2, fontsize=9.5)
    ax.set_xscale("log")
    ax.set_yticks([0, 1])
    ax.set_yticklabels([p[0] for p in pairs])
    ax.set_xlim(0.5, max(d["median_minutes_to_merge"] for _, d, _ in pairs) * 26)
    ax.set_title("agent PR 的合并耗时中位：两个数量级的差距", fontsize=12, pad=12,
                 loc="left")
    finish(ax, xlabel="创建到合并的分钟数（对数刻度）", xgrid=True)
    save(fig, "fig06_agent_pr_merge_latency.png")


# ---------------------------------------------------------------- fig07
def fig07_case_a_states() -> None:
    """案例 A：把 review 过程显式化为状态机后的时序带。分类系列 ≤6，按槽位固定取色。"""
    rows = table("t06_case_a_label_flow.csv")
    ca = S.get("case_a")
    if not rows or not ca:
        return
    from datetime import datetime
    ev = [(r["event"][0], r["event"][1:],
           datetime.strptime(r["at"], "%Y-%m-%dT%H:%M:%SZ")) for r in rows]
    t0 = ev[0][2]
    states = [s for s in ca["distinct_state_labels"]]
    color_of = {s: C[i % len(C)] for i, s in enumerate(states)}
    spans: dict[str, list[tuple[float, float]]] = {s: [] for s in states}
    open_at: dict[str, float] = {}
    end = max(e[2] for e in ev)
    for sign, name, t in ev:
        if name not in spans:
            continue
        d = (t - t0).total_seconds() / 86400
        if sign == "+":
            open_at[name] = d
        elif name in open_at:
            spans[name].append((open_at.pop(name), d))
    for name, d in open_at.items():
        spans[name].append((d, (end - t0).total_seconds() / 86400))
    fig, ax = plt.subplots(figsize=(10.2, 3.4))
    for i, s in enumerate(states):
        for a, b in spans[s]:
            ax.barh(i, max(b - a, 0.45), left=a, height=0.46, color=color_of[s],
                    linewidth=0, zorder=3)
    ax.set_yticks(list(range(len(states))))
    ax.set_yticklabels(states, fontsize=9.5)
    ax.invert_yaxis()
    ax.set_xlim(-1, (end - t0).total_seconds() / 86400 + 2)
    ax.set_title(f'案例 A：{ca["repo"]}#{ca["number"]} 的状态占用时序'
                 f'（{ca["days"]:.0f} 天，{ca["n_approved"]} 次批准）',
                 fontsize=12, pad=12, loc="left")
    finish(ax, xlabel="自 PR 创建起的天数", xgrid=True)
    save(fig, "fig07_case_a_state_timeline.png")


# ---------------------------------------------------------------- fig08
def fig08_case_b_actors() -> None:
    """案例 B：review 提交与 thread 开启的归属分解。两个不同测度 → 小多图。"""
    cb = S.get("case_b")
    if not cb:
        return
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 3.4))
    ax = axes[0]
    items = list(cb["reviews_by_author"].items())[:6]
    for i, (who, n) in enumerate(items):
        color = C[0] if who in cb["human_reviewer_logins"] else C[1]
        rbar(ax, i, n, color)
        ax.text(n + 0.8, i, str(n), va="center", color=INK2, fontsize=9.5)
    ax.set_yticks(list(range(len(items))))
    ax.set_yticklabels([w for w, _ in items], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, max(n for _, n in items) * 1.2)
    ax.set_title("review 提交次数", fontsize=11, pad=10, loc="left")
    ax.legend(handles=[Line2D([], [], color=C[0], lw=6, label="人类"),
                       Line2D([], [], color=C[1], lw=6, label="bot / agent")],
              loc="lower right", ncol=2, fontsize=9)
    finish(ax, xgrid=True)
    ax = axes[1]
    op = list(cb["thread_openers"].items())[:6]
    for i, (who, n) in enumerate(op):
        rbar(ax, i, n, C[0] if who in cb["human_reviewer_logins"] else C[1])
        ax.text(n + 0.4, i, str(n), va="center", color=INK2, fontsize=9.5)
    ax.set_yticks(list(range(len(op))))
    ax.set_yticklabels([w for w, _ in op], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, max(n for _, n in op) * 1.25)
    ax.set_title(f'开启 review thread 的人（共 {cb["n_threads"]} 条，'
                 f'{cb["threads_resolved"]} 条已解决）', fontsize=11, pad=10, loc="left")
    finish(ax, xgrid=True)
    fig.suptitle(f'案例 B：{cb["repo"]}#{cb["number"]}——谁在说话，与谁在提出问题',
                 fontsize=12.5, x=0.045, ha="left", y=1.06)
    save(fig, "fig08_case_b_actor_decomposition.png")


# ---------------------------------------------------------------- fig09
def fig09_case_b_ai_reviewer() -> None:
    """案例 B：AI reviewer 的产出构成。二分构成 → 单条百分堆叠 + 主数字，不用饼图。"""
    cb = S.get("case_b")
    if not cb or not cb.get("ai_reviewer_submissions"):
        return
    tot = cb["ai_reviewer_submissions"]
    mal, sub = cb["ai_reviewer_malfunction"], cb["ai_reviewer_substantive"]
    fig, ax = plt.subplots(figsize=(8.8, 2.4))
    ax.barh(0, mal, height=0.42, color=STATUS_CRIT, linewidth=0, zorder=3)
    if sub:
        ax.barh(0, sub, left=mal + 0.25, height=0.42, color=C[2], linewidth=0, zorder=3)
    ax.text(mal / 2, 0, f"机械失败模板 {mal}", ha="center", va="center", color="#ffffff",
            fontsize=10, zorder=4)
    if sub:
        ax.text(mal + sub / 2, 0, f"其他 {sub}", ha="center", va="center", color=INK,
                fontsize=10, zorder=4)
    ax.text(0, 0.62, f"{tot}", fontsize=30, color=INK, va="bottom")
    ax.text(0, 0.55, f"    次 review 提交，来自 {cb['ai_reviewer_login']}", fontsize=10,
            color=INK2, va="bottom")
    ax.set_ylim(-0.5, 1.5)
    ax.set_xlim(0, tot * 1.02)
    ax.set_yticks([])
    ax.set_title("案例 B 中「AI reviewer」的实际产出", fontsize=12, pad=26, loc="left")
    finish(ax, xlabel="按 review 提交条数")
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_xticks([])
    save(fig, "fig09_case_b_ai_reviewer_output.png")


# ---------------------------------------------------------------- fig10
def fig10_bot_signal() -> None:
    """D7：各 bot reviewer 的实质内容占比，附人类基线参考线。单一测度 → 单色 + 强调。"""
    rows = table("t08_bot_review_signal.csv")
    if not rows:
        return
    rows = [r for r in rows if int(r["bodies"]) >= 3][:10]
    if not rows:
        return
    rows = sorted(rows, key=lambda r: float(r["substantive_pct"]))
    fig, ax = plt.subplots(figsize=(9.2, max(2.6, 0.46 * len(rows) + 1.5)))
    for i, r in enumerate(rows):
        v = float(r["substantive_pct"])
        rbar(ax, i, v, C[0] if v >= 65.5 else C[1])
        ax.text(v + 1.5, i, f'{v:.0f}%  (n={r["bodies"]})', va="center", color=INK2,
                fontsize=9)
    ax.axvline(65.5, color=MUTED, linewidth=1.2, zorder=2)
    ax.text(65.5, len(rows) - 0.35, "  人类 reviewer 有用率基线 65.5%", color=INK2,
            fontsize=9, va="top")
    ax.set_yticks(list(range(len(rows))))
    ax.set_yticklabels([r["reviewer"] for r in rows], fontsize=9)
    ax.set_xlim(0, 118)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%" if v <= 100 else ""))
    ax.set_title("bot reviewer 的输出里有多少不是机械失败模板", fontsize=12, pad=12,
                 loc="left")
    finish(ax, xlabel="非机械失败模板的占比（该指标是实质内容占比的上界）", xgrid=True)
    save(fig, "fig10_bot_review_signal.png")


# ---------------------------------------------------------------- fig11
def fig11_revert() -> None:
    """D4：revert 率。单一测度 → 单色 + 合计参考线。"""
    rows = table("t05_revert_rate.csv")
    if not rows:
        return
    rows = sorted(rows, key=lambda r: float(r["revert_pct"]))
    fig, ax = plt.subplots(figsize=(8.6, 2.9))
    for i, r in enumerate(rows):
        v = float(r["revert_pct"])
        rbar(ax, i, v, C[0])
        ax.text(v + 0.03, i, f'{v:.2f}%   ({r["revert_titled"]}/{r["merged_total"]})',
                va="center", color=INK2, fontsize=9.5)
    pooled = S.get("d4_pooled_pct", 0)
    ax.axvline(pooled, color=MUTED, linewidth=1.2, zorder=2)
    ax.text(pooled, len(rows) - 0.4, f"  合计 {pooled:.2f}%", color=INK2, fontsize=9,
            va="top")
    ax.set_yticks(list(range(len(rows))))
    ax.set_yticklabels([short(r["repo"]) for r in rows])
    ax.set_xlim(0, max(float(r["revert_pct"]) for r in rows) * 1.55)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.1f}%"))
    ax.set_title(f'「先合并、事后修」的代价：标题含 Revert 的 PR 占比（{S.get("d4_since","")} 起）',
                 fontsize=12, pad=12, loc="left")
    finish(ax, xlabel="占同期已合并 PR 的比例", xgrid=True)
    save(fig, "fig11_revert_rate.png")


# ---------------------------------------------------------------- fig12
def fig12_literature_timeline() -> None:
    """文献时效性：数据窗口与发表时点、基准日的关系。单轴时间线。"""
    fig, ax = plt.subplots(figsize=(10.2, 3.4))
    items = [
        ("Google 案例研究的数据窗口\n（sadowski2018）", 2014.0, 2016.58, C[2]),
        ("AIDev 数据采集窗口\n（截止 2025-08-01）", 2025.0, 2025.58, C[1]),
        ("基于 AIDev 的各实证论文发表\n（2026 年）", 2026.0, 2026.6, C[0]),
    ]
    for i, (name, a, b, color) in enumerate(items):
        ax.barh(i, b - a, left=a, height=0.4, color=color, linewidth=0, zorder=3)
        ax.text(b + 0.06, i, name, va="center", color=INK2, fontsize=9)
    base = 2026.59
    ax.axvline(base, color=STATUS_CRIT, linewidth=1.6, zorder=4)
    ax.text(base, 2.62, f'  本报告基准日 {S.get("baseline_date","")}', color=STATUS_CRIT,
            fontsize=9.5, va="bottom")
    ax.annotate("", xy=(2026.59, -0.62), xytext=(2025.58, -0.62),
                arrowprops=dict(arrowstyle="<->", color=MUTED, lw=1.2))
    ax.text(2026.08, -0.78, "AI 侧证据与基准日之间约 12 个月", ha="center", color=INK2,
            fontsize=9.5, va="top")
    ax.set_yticks([])
    ax.set_ylim(-1.5, 3.1)
    ax.set_xlim(2013.6, 2028.6)
    ax.set_xticks([2014, 2016, 2018, 2020, 2022, 2024, 2025, 2026])
    ax.set_xticklabels(["2014", "2016", "2018", "2020", "2022", "2024", "2025", "2026"])
    ax.set_title("引用文献的证据窗口与本报告基准日的关系", fontsize=12, pad=12, loc="left")
    finish(ax, xgrid=True)
    for side in ("left",):
        ax.spines[side].set_visible(False)
    save(fig, "fig12_literature_validity_window.png")


# ---------------------------------------------------------------- fig13
def fig13_stability_region() -> None:
    """迭代的稳定判据 ECR/EIR > Acc/(1-Acc) 在 (EIR, ECR) 平面上的分界。"""
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    xs = [i / 400 for i in range(1, 121)]          # EIR 0.25%–30%
    for acc, color, name in ((0.80, C[2], "Acc = 0.80"), (0.95, C[1], "Acc = 0.95"),
                             (0.99, C[0], "Acc = 0.99")):
        k = acc / (1 - acc)
        ys = [min(x * k, 1.0) for x in xs]
        ax.plot([x * 100 for x in xs], [y * 100 for y in ys], color=color, linewidth=1.9,
                label=name, solid_capstyle="round", zorder=3)
    ax.axvline(0.5, color=MUTED, linewidth=1.2, zorder=2)
    ax.text(0.62, 96, "文献实测的经验阈值 EIR ≈ 0.5%", color=INK2, fontsize=9, va="top")
    ax.text(6.5, 30, "此线以上：迭代净收益为正", color=INK2, fontsize=9.5)
    ax.text(12.5, 8, "此线以下：迭代净收益为负\n（改坏的比改好的多）", color=INK2,
            fontsize=9.5)
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 100)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_title("何时应当再迭代一轮：EIR–ECR 平面上的分界线", fontsize=12, pad=12,
                 loc="left")
    ax.legend(loc="lower right", fontsize=9.5)
    finish(ax, xlabel="EIR（把对的改错的比率）", ylabel="ECR（把错的改对的比率）",
           xgrid=True, ygrid=True)
    save(fig, "fig13_iteration_stability_region.png")


# ---------------------------------------------------------------- fig17
def fig17_blocked_fate() -> None:
    """D9：逐仓库的 P(最终未合并 | 曾被正式阻塞)。单一测度 → 单色 + 灰化不稳估计。"""
    rows = table("t12_blocked_pr_fate_by_repo.csv")
    if not rows:
        return
    rows = sorted(rows, key=lambda r: float(r["pct_closed_given_blocked"]))
    fig, ax = plt.subplots(figsize=(9.0, 3.0))
    for i, r in enumerate(rows):
        v = float(r["pct_closed_given_blocked"])
        unstable = r["estimate_unstable"] == "True"
        rbar(ax, i, v, BASE if unstable else C[0])
        ax.text(v + 1.6, i, f"{v:.1f}%" + ("（估计不稳）" if unstable else ""),
                va="center", color=INK2, fontsize=9.5)
    ax.set_yticks(list(range(len(rows))))
    ax.set_yticklabels([short(r["repo"]) for r in rows], fontsize=10)
    ax.set_xlim(0, 128)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%" if v <= 100 else ""))
    ax.invert_yaxis()
    ax.set_title("「阻塞」在不同项目里不是同一件事：被阻塞后未合并的概率相差近 10 倍",
                 fontsize=12, pad=12, loc="left")
    finish(ax, xlabel="P(最终未合并 | 曾收到 CHANGES_REQUESTED)，按总体基数加权", xgrid=True)
    save(fig, "fig17_blocked_pr_fate_by_repo.png")


# ---------------------------------------------------------------- fig18
def fig18_block_limbo() -> None:
    """D9：阻塞之后的三条路，同一量纲（天）故可同轴对比。对数刻度，跨度达三个数量级。"""
    if not S.get("d9_present"):
        return
    items = [
        (f'走出来了：被阻塞但最终合并\nn={S["d9_n_blocked_merged"]}',
         S["d9_merged_median_days_create_to_merge"], C[2]),
        (f'对照：从未被阻塞、关闭未合并\nn={S["d9_unblocked_closed_n"]}',
         S["d9_unblocked_closed_median_days"], BASE),
        (f'没走出来：被阻塞且最终关闭\nn={S["d9_n_blocked_closed"]}',
         S["d9_closed_median_days"], STATUS_CRIT),
    ]
    fig, ax = plt.subplots(figsize=(9.0, 3.2))
    for i, (lab, v, col) in enumerate(items):
        ax.barh(i, v, height=0.5, color=col, linewidth=0, zorder=3)
        ax.text(v * 1.12, i, f"{v} 天", va="center", color=INK2, fontsize=10)
    ax.set_yticks(list(range(len(items))))
    ax.set_yticklabels([x[0] for x in items], fontsize=9.2)
    ax.set_xscale("log")
    ax.set_xlim(0.8, 400)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.invert_yaxis()
    ax.set_title(f'阻塞不产生裁决，产生悬置：死掉的一侧比对照组多耗 {S["d9_rot_ratio"]} 倍时间',
                 fontsize=12, pad=12, loc="left")
    finish(ax, xlabel="从创建到终态的中位天数（对数刻度，三组同口径）", xgrid=True)
    save(fig, "fig18_block_limbo.png")


# ---------------------------------------------------------------- fig16
def fig16_self_review() -> None:
    """两次变更周期各自的 |B_n| 曲线（§9.2、§9.4）。

    两个系列同为「开放的阻塞级发现数」，同轴同量纲，故可并列而无需双轴。数值来自
    audit/self_review_log.csv，与 report.md 的逐条清单一一对应，由 verify.py 核对。
    """
    p = ROOT / "audit" / "self_review_log.csv"
    if not p.exists():
        return
    with p.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    cycles = sorted({int(r["cycle"]) for r in rows})
    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    for k, cy in enumerate(cycles):
        rs = [r for r in rows if int(r["cycle"]) == cy]
        xs = [int(r["round"]) for r in rs]
        ys = [int(r["blocking_open"]) for r in rs]
        names = {1: "正文与数据", 2: "引用体系", 3: "出口集合（范围固定后）"}
        ax.plot(xs, ys, color=C[k], linewidth=2, marker="o", markersize=9,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=3,
                label=f"周期 {cy}：{names.get(cy, cy)}")
        for x, y in zip(xs, ys):
            ax.annotate(f"|B_{x-1}| = {y}", (x, y), textcoords="offset points",
                        xytext=(0, 12), ha="center", color=INK2, fontsize=9.5)
    xs_all = sorted({int(r["round"]) for r in rows})
    ax.set_xticks(xs_all)
    ax.set_xticklabels([f"第 {x} 轮" for x in xs_all])
    ax.set_ylim(-0.8, max(int(r["blocking_open"]) for r in rows) + 1.4)
    ax.set_xlim(min(xs_all) - 0.4, max(xs_all) + 0.4)
    ax.set_title("三次变更周期的自审：阻塞级发现数均严格递减至 0（不变量 M，轮数上限 3）",
                 fontsize=11.5, pad=12, loc="left")
    ax.legend(loc="upper right", fontsize=9)
    finish(ax, ylabel="开放的阻塞级发现数 |B_n|", ygrid=True)
    save(fig, "fig16_self_review_convergence.png")


def main() -> None:
    for fn in (fig01_changes_requested, fig02_review_submissions, fig03_closed_prs,
               fig04_gate_strength, fig05_agent_two_worlds, fig06_agent_latency,
               fig07_case_a_states, fig08_case_b_actors, fig09_case_b_ai_reviewer,
               fig10_bot_signal, fig11_revert, fig12_literature_timeline,
               fig13_stability_region, fig14_offchannel, fig15_cluster_sensitivity, fig17_blocked_fate,
               fig18_block_limbo, fig16_self_review):
        try:
            fn()
        except Exception as exc:                      # noqa: BLE001
            print(f"  !! {fn.__name__} 失败：{type(exc).__name__}: {exc}")
    print(f"figures/：{len(list(FIG.glob('*.png')))} 张")


if __name__ == "__main__":
    main()
