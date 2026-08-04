# PR 评审循环的有穷性研究

> 基准日 **2026-08-04** ｜ 一手数据 **2,997 个不同 PR / 102 次 GraphQL 调用** ｜ 图 **16 张** ｜ 可复算表 **11 张** ｜ 机器核对断言 **195 条**（`python3 scripts/verify.py`）｜ 参考文献 **34 条**（全文核对文献 **22 篇**，撤销引用 **6 条**）

「作者提交 → 评审者提意见 → 作者修改 → 评审者再提意见」这个循环凭什么会停？本仓库用可审计的一手数据、逐字核对的文献、以及两个真实 PR 的完整事件流回答这个问题，并给出一套**不自建 agent 框架**、只在 Claude Code / Codex 这类成品 harness 内可执行的协议。

**完整报告：[`report.md`](report.md)**

---

## 主要结论

| # | 结论 | 证据 |
|---|---|---|
| 1 | **有穷性是协议属性，不是能力属性。** 评审循环没有内生终止保证；终止必须来自对评审算子的外部约束。「等模型更强」解决不了这个问题 | [§2](report.md#2-形式化)、[§4.1](report.md#41-判据) |
| 2 | **成熟项目从不靠「改到没意见」终止。** 97.8% 的已合并 PR 从未出现过一次正式阻塞态，review 提交中位为 1 | [§5.1](report.md#51-合并侧正式阻塞态是稀有事件)、图 1–2 |
| 3 | **现实中不收敛的终止方式是超时与放弃。** 关闭未合并的一侧：51.2% 从未被 review、22.4% 带生命周期标签、p90 开放 316.6 天 | [§5.2](report.md#52-未合并侧现实中的终止方式是超时与放弃)、图 3 |
| 4 | **「带瑕疵合并 + 事后修」的代价约 0.76% 回滚率。** 用约 1% 的回滚换掉绝大多数第 N 轮评审 | [§5.3](report.md#53-移出本-pr-的价格revert-率)、图 11 |
| 5 | **长 ≠ 不收敛。** 112 天的 PR 只需 1 次批准、0 次阻塞态；3.3 天的 PR 却有 20 次空转、4 次回退 | [§5.4](report.md#54-案例-a一个-112-天但完全收敛的-pr)、[§7.4](report.md#74-案例-bai-写ai-评审全程空转人类仲裁终止)、图 7–9 |
| 6 | **当下 AI 评审的问题主要在集成，不在模型。** 实测机器人 review 正文 56.45% 是机械失败模板，且静默持续了 50 个 PR 无人关闭 | [§7.3](report.md#73-ai-reviewer-的信噪比当下实测)、图 10 |
| 7 | **评判 AI reviewer 的目标线是 64%–68%，不是 100%。** 这是人类 reviewer 评论有用率的实证基线 | [§7.3](report.md#73-ai-reviewer-的信噪比当下实测) |
| 8 | **agent 侧唯一稳健的结论是分层的。** 低成熟度仓库中 agent PR 约 22% 无任何 review 与评论即合并（人类基线 4.2%–4.6%）；成熟仓库样本不足以支持任何跨组比较 | [§7.1](report.md#71-分层结果)–[§7.2](report.md#72-成熟层的聚簇一个足以推翻跨层比较的问题)、图 4–5、15 |
| 9 | **落地不需要造框架。** 成品 harness 已把四类终止机制产品化；要做的是铺满 verifier、把 AI review 排在人类之前、把预算落到不可绕过的层 | [§8](report.md#8-边界内的解决方案) |

## 两处方法学修正（值得单独看）

这两处都足以让一个看似干净的结论完全反向，也是本仓库自审流程实际检出的问题：

- **`reviews.totalCount == 0` 不等于「无人过目」。** 143 个「零正式 review」的已合并 PR 中，120 个（83.92%）可归因于 Prow `/lgtm`、bors `r+`、自动 backport 三条旁路批准通道。→ [§3.4](report.md#34-测量效度两处会颠覆结论的缺陷及其修正)、图 14
- **agent 成熟层的 78 个 PR 不是独立观测。** 23 个「零关注」PR 中 20 个来自同一仓库；留一仓库刀切后该层比率在 5.36%–33.33% 之间摆动，跨层比较不成立。→ [§7.2](report.md#72-成熟层的聚簇一个足以推翻跨层比较的问题)、图 15

同一个结论被后续数据**连续否定两次**（n=16 → n=78 → 聚簇诊断），过程完整记录在 [§7.2](report.md#72-成熟层的聚簇一个足以推翻跨层比较的问题) 与 [§9.2](report.md#92-第一个变更周期正文与数据)。

## 目录结构

```
report.md                     学术正文（问题形式化 → 实证 → 机制归纳 → 方案 → 自指检验 → 局限）
raw/                          一手数据，GraphQL 原始响应逐字落盘，未经筛选或编辑
  d1_merged_prs.json            5 仓库 × 100 个已合并 PR
  d2_closed_prs.json            5 仓库 × 100 个关闭未合并 PR
  d3_agent_prs.json             4 个 agent 的 1,600 + 400 个 PR
  d4_reverts.json               4 仓库的 revert 比例分子分母
  d5_cases.json                 两个案例 PR 的完整事件流
  d7_bot_review_text.json       259 条 review 正文
  d8_d1_authors.json            D1 全部 PR 的作者身份（旁路批准归因用）
  manifest.json                 102 次 API 调用的记录与 4 处采集缺口
derived/
  stats.json                    93 个统计量，正文所有数字的唯一来源
  tables/*.csv                  11 张可复算表
figures/*.png                   16 张图
references.bib                  34 条参考文献的 BibTeX（由脚本生成，勿手工编辑）
CITATION.cff                    本仓库自身的引用信息，GitHub 据此渲染 "Cite this repository"
lit/
  manifest.csv                  22 篇文献的 URL / 字节数 / SHA-256
  references.json               自 arXiv / DBLP 取回的完整著录信息 + 取回日期
  quotes.md                     逐字引文档案 + §9 已撤销的 6 条引用 + §10 未引用数值的文献
audit/
  palette_validation.md         配色校验器输出
  math_render_audit.md          LaTeX 渲染审计：19 处缺陷的清单、证据与修法
  self_review_log.csv           自审的 |B_n| 曲线原始记录
scripts/
  collect.py                    D1–D5、D7 采集
  collect_d2_nodejs_fallback.py D2 的 nodejs/node 降级取数路径
  collect_d8_authors.py         D8 采集
  fetch_literature.py           22 篇全文下载与校验和
  fetch_citation_metadata.py    自 arXiv / DBLP 取回著录信息
  gen_references.py             生成参考文献表与 references.bib，回填 report.md
  lit_digest.py                 文献全文检索工具
  check_math.py                 Markdown 中 LaTeX 写法检查（E1–E6，CI 会跑）
  check_rendered.py             抓 GitHub 渲染结果核对公式/表格/图片（发布后手动跑）
  analyze.py                    raw/ → derived/
  plot.py                       derived/ → figures/
  verify.py                     正文 × derived/ 的 195 条断言核对
```

## 复现

离线重算（不需要网络，从落盘原始数据出发）：

```bash
python3 scripts/analyze.py         # raw/ → derived/stats.json + derived/tables/*.csv
python3 scripts/plot.py            # derived/ → figures/*.png
python3 scripts/gen_references.py  # lit/references.json → 参考文献表 + references.bib
python3 scripts/verify.py          # 正文的每个数字与每条引用 vs 落盘数据
```

重新采集（会产生新的基准日，数值将与本文不同，需要 `gh` 已登录）：

```bash
python3 scripts/collect.py
python3 scripts/collect_d2_nodejs_fallback.py
python3 scripts/collect_d8_authors.py
python3 scripts/fetch_literature.py
python3 scripts/fetch_citation_metadata.py
```

依赖：Python 3.10+、`matplotlib`、`gh`（GitHub CLI，已认证）、CJK 字体（`Noto Sans CJK SC` 或等价）。

## 可审计性约定

1. **正文中的每个数字都必须来自 `derived/stats.json`**，由 `scripts/verify.py` 逐条比对；断言总数本身也被核对（正文声明的条数必须等于实际执行的条数）。
2. **每条文献数值必须先在 `lit/quotes.md` 登记逐字原文**；未能在全文中定位的一律撤销并记入该文件 §9。本次撤销 6 条。
3. **采集缺口显式记录而非缩小分母**，见 `raw/manifest.json` 的 `gaps` 字段与 [§3.3](report.md#33-采集缺口的显式记录)。
4. **口径偏差标注方向**：每个可能有偏的指标都注明它是高估还是低估，见 [§10](report.md#10-局限)。
5. **参考文献不手写**：著录信息自 arXiv 与 DBLP 接口取回并落盘于 `lit/references.json`，文献表与 BibTeX 由脚本生成；正文引用写作 `[[18]](#ref-sadowski2018)`，链接目标带 key，因此「编号 ↔ 文献」的映射可被机器核对（无孤儿引用、无未被引用条目）。
6. **本仓库自身按报告推导的协议评审**：verifier 先行、只有带证据的发现构成阻塞、轮数上限 3、未处理项移出为 follow-up。过程见 [§9](report.md#9-自指检验本报告自身的评审过程)，配置见 [`REVIEW.md`](REVIEW.md)。

## 局限

覆盖 5 个大型基础设施仓库与 4 个以 App 身份提交 PR 的 agent，单一时间截面。Cursor 与 Codex 在多数集成模式下以用户身份提交，结构上不可按作者检索，因此 agent 侧样本对当前生态有偏。不做假设检验，只报告描述统计与稳健性诊断。方案章节大量引用官方文档且报告由 Claude Code 生成，存在利益相关性，对冲措施与残余风险见 [§10](report.md#10-局限)。

## 引用

本仓库根目录的 `CITATION.cff` 采用 Citation File Format 1.2.0，GitHub 会解析它并在首页右侧渲染 **"Cite this repository"**，可直接导出 APA 与 BibTeX。

**引用时请注明基准日与提交哈希**：全部数值绑定在 2026-08-04 这一次采集上，重新运行 `scripts/collect.py` 会得到不同的数值。

报告所引的 34 条参考文献见 [报告附录 D](report.md#附录-d参考文献)，机器可读版本见 [`references.bib`](references.bib)。

## 许可

数据与代码按 MIT 许可提供。第三方论文全文不随本仓库分发，仅提供 URL 与 SHA-256 校验和。
