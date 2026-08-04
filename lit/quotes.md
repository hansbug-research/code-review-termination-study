# 引文档案

本报告引用的每一条文献数值，其在原文中的确切措辞记录于此。全文获取方式与校验和见 [manifest.csv](manifest.csv)；arXiv 条目取 e-print 源码包（LaTeX 原文），非 arXiv 条目取出版方或作者提供的 PDF 全文。第三方论文本身不随本仓库分发。

规则：本报告正文只允许引用本文件中出现过的措辞所支持的数值。凡是在核对中未能于原文定位的数值，一律记入文末「§9 已撤销的引用」并从正文移除。

---

## 1. AI coding agent 的 PR 数据基础

### 1.1 AIDev 数据集（arXiv 2602.09185）

> AIDev aggregates 932,791 Agentic-PRs produced by five agents: OpenAI Codex, Devin, GitHub Copilot, Cursor, and Claude Code. These PRs span 116,211 repositories and involve 72,189 developers. In addition, AIDev includes a curated subset of 33,596 Agentic-PRs from 2,807 repositories with over 100 stars.

正文（§4.1）用于确立时效性的关键一句，位于正文对数据集的复述处：

> \aidev comprises 932,791 \agentprs authored by five agents: \codex, \devin, \copilot, \cursor, and \claude, across 116,211 repositories involving 72,189 developers (**dataset cutoff: August 1, 2025**).

`\aidev`、`\agentprs` 等为该文自定义宏，展开后分别为 AIDev、Agentic-PRs 与五个 agent 名。**「dataset cutoff: August 1, 2025」是本报告全部时效性论证的承重引文**。

### 1.2 各 agent 的 PR 接受率（arXiv 2602.08915）

> This paper presents an empirical study comparing five popular agents (OpenAI Codex, GitHub Copilot, Devin, Cursor, and Claude Code), analyzing 7,156 pull requests (PRs) from the AIDev dataset. … Our analysis suggests that the PR task type is a dominant factor influencing acceptance rates: documentation tasks achieve 82.1% acceptance compared to 66.1% for new features—a 16 percentage point gap that exceeds typical inter-agent variance for most tasks. OpenAI Codex achieves consistently high acceptance rates across all nine task categories (59.6%–88.6%) … However, no single agent performs best across all task types: Claude Code leads in documentation (92.3%) and features (72.6%), while Cursor excels in fix tasks (80.4%).

> Devin exhibits the only consistent positive trend in acceptance rate (+0.77% per week over 32 weeks), whereas other agents remain largely stable.

本报告据此主张的是「任务类型比 agent 身份更能解释接受率差异」，而非任何单一 agent 的总体排名（见 §9.2）。

### 1.3 agent 修复被拒的原因（arXiv 2606.13468）

> From a first exploration of the AIDev dataset, we find that 46.41% of the fixes proposed by the agents Copilot, Devin, Cursor, and Claude are rejected. … we conduct a qualitative study on a representative sample of 306 non-merged pull requests … Our qualitative findings identify 14 reasons divided into four high-level categories for rejecting AI-agent fixes. We observe that developers can reject fixes due to fixes whose implementation is incorrect (e.g., incomplete, wrong approach), fixes that do not pass the continuous integration (CI) pipelines and fail tests, fixes for which the agent is unable to perform the implementation (e.g., no code generated, sessions lost), and fixes whose priority is low.

作者给出的改进方向，与本报告 §7 的 verifier 前置主张同向：

> (1) proposing hints about the approach to follow for fixing an issue, (2) outlining constraints or limitations regarding the approaches that should not be taken, and (3) instructing the agent on how to validate the implementation through CI pipelines and without introducing a breaking change.

### 1.4 code review agent 的信噪比与合并率（arXiv 2604.03196）

> From AIDev's 19,450 PRs, we analyze 3,109 unique PRs in Commented review state, comparing human-only versus CRA-only reviews. We examine 98 closed CRA-only PRs to assess whether low signal-to-noise ratios contribute to abandonment. CRA-only PRs achieve a 45.20% merge rate, 23.17 percentage points lower than human-only PRs (68.37%), with significantly higher abandonment. Our signal-to-noise analysis reveals that 60.2% of closed CRA-only PRs fall into the 0–30% signal range, and 12 of 13 CRAs exhibit average signal ratios below 60%, indicating substantial noise in automated review feedback.

> The test yields $\chi^2 = 83.0319$ with 8 degrees of freedom and $p < 0.001$, demonstrating a statistically significant association between reviewer type and merge outcomes.

> For practitioners, our results indicate that CRAs should augment rather than replace human reviewers, and that human involvement remains critical for effective and actionable code review.

规模背景：

> OpenAI Codex alone created over 400,000 pull requests in open-source GitHub repositories in less than two months since its release.

### 1.5 开发者对 agentic review 的实际反应（arXiv 2607.03316）

> Through an empirical study of 31,073 pairs of code reviews and developer feedback from 10,191 pull requests across 239 GitHub repositories, our results show that agentic reviews receive mixed reception: 36.4% were accepted and 7.3% triggered discussion, while 56.3% were rejected. Rejections were primarily associated with invalid suggestions that were false positives, redundant, or out of scope, as well as misalignment with developer intent and coding practices. We further found that agentic reviews tend to focus more on functional concerns than evolvability-related comments, yet they were more likely to be invalid.

> We found that lightweight learning-based methods achieve up to 76% F1 score, suggesting learnable patterns exist between code reviews and their corresponding feedback.

### 1.6 人类审查 agent 代码时的习惯化（arXiv 2606.22721）

> We conduct a longitudinal within-reviewer analysis using the \aidev dataset, studying 400 repeat reviewers who collectively submitted 11,429 reviews over a seven-month observation period. Comparing each reviewer's early and late review episodes, we observe a population-level shift in approval rate from 30.1% to 36.8% (Wilcoxon signed-rank $p < 10^{-6}$ on paired shifts). Pooled by within-reviewer experience decile, the cumulative gap reaches +14.5 pp from first to tenth decile. This shift is experience-driven (persists after controlling for calendar time), agent-specific (human PR approval rates decline over the same period), and not explained by PR difficulty (median PR size is flat). However, review latency increases rather than decreases (+3.5×), while inline comment volume decreases (−22%, $p=0.0014$), suggesting reviewers spend more time in queue but less time actively inspecting code. The combination of rising approval, declining comment effort, and increasing queue time is most consistent with reflexive habituation under growing workload rather than rational trust calibration alone.

覆盖范围与对照组：

> The dataset contains 16,895 human reviews across 2,494 unique reviewers, covering five agent systems: GitHub Copilot Autofix, Devin (Cognition AI), OpenAI Codex CLI, Cursor, and Claude Code (Anthropic).

> To distinguish reviewer-general leniency from agent-specific adaptation, we crawled review records for 6,618 human-authored PRs from the same repositories via the GitHub API, obtaining 11,415 reviews from 1,851 reviewers.

> Monthly median PR size (lines changed) does not decline over the observation window (Spearman $\rho=+0.02$, $p=0.009$, negligible magnitude).

---

## 2. 迭代与终止的机制性证据

### 2.1 自我纠错的稳定性判据（arXiv 2604.22273）

> We recast self-correction as a closed-loop feedback-control problem in which the same model is both controller and plant, and analyze its error dynamics via a two-state Markov model over {Correct, Incorrect}, parameterized by the Error Introduction Rate (EIR) and Error Correction Rate (ECR). The model yields a directly measurable stability threshold—iterate only when $\mathrm{ECR}/\mathrm{EIR} > \mathrm{Acc}/(1-\mathrm{Acc})$—in which EIR acts as a stability margin and prompting becomes lightweight controller design.

> Empirically, across 7 models and 3 datasets (GSM8K, MATH, StrategyQA), a sharp near-zero EIR boundary ($\lesssim 0.5\%$) cleanly separates beneficial from harmful self-correction: only o3-mini ($+3.4$ pp), Claude Opus 4.6 ($+0.6$ pp), and o4-mini ($\pm 0$ pp) stay non-degrading, while GPT-5 and four others lose accuracy.

> A verify-first prompt intervention then provides causal evidence: it drives GPT-4o-mini's EIR from 2% to 0% and converts a $-6.2$ pp degradation into $+0.2$ pp (paired McNemar, $p<10^{-4}$), with negligible change on already-sub-threshold models—exactly as the diagnostic predicts.

> A complementary analysis of adaptive self-consistency (ASC) shows it halts harmful refinement at a $3.8$ pp confidence-elicitation cost, exposing a two-tier capability structure: prompt-level EIR suppression prevents degradation, whereas ECR enhancement—plausibly training-level—is required for genuine gains. Self-correction should thus be treated not as a default behavior but as a control decision governed by measurable error dynamics.

形式化定义（原文 Definition）：

> At iteration $k$, the Error Introduction Rate (EIR) and Error Correction Rate (ECR) are: $\text{EIR}(k) = P(c_i^{(k+1)} = 0 \mid c_i^{(k)} = 1)$, $\text{ECR}(k) = P(c_i^{(k+1)} = 1 \mid c_i^{(k)} = 0)$. The Net Benefit is $\text{NB}(k) = \text{Acc}(k) - \text{Acc}(k-1)$.

> The net benefit is zero ($\text{NB}(k+1) = 0$) if and only if: $\frac{\text{ECR}(k)}{\text{EIR}(k)} = \frac{\text{Acc}(k)}{1 - \text{Acc}(k)}$

> If $\text{EIR}(k) \to \text{EIR}^*$ and $\text{ECR}(k) \to \text{ECR}^*$, the steady-state accuracy is: $\pi^* = \frac{\text{ECR}^*}{\text{EIR}^* + \text{ECR}^*}$

> Under stationary rates, convergence is geometric: $|\text{Acc}(k) - \pi^*| = |1 - \text{EIR}^* - \text{ECR}^*|^k \cdot |\text{Acc}(0) - \pi^*|$

操作建议：

> measure EIR on a calibration set, check whether the equilibrium condition is satisfied, and iterate only if it is.

### 2.2 内生自我纠错的原始否定结果（arXiv 2310.01798）

原文 Table（GSM8K / CommonSenseQA / HotpotQA，# calls 为模型调用次数）：

| 模型 | 方法 | # calls | GSM8K | CommonSenseQA | HotpotQA |
|---|---|---:|---:|---:|---:|
| GPT-3.5 | Standard Prompting | 1 | 75.9 | 75.8 | 26.0 |
| GPT-3.5 | Self-Correct (round 1) | 3 | 75.1 | 38.1 | 25.0 |
| GPT-3.5 | Self-Correct (round 2) | 5 | 74.7 | 41.8 | 25.0 |
| GPT-4 | Standard Prompting | 1 | 95.5 | 82.0 | 49.0 |
| GPT-4 | Self-Correct (round 1) | 3 | 91.5 | 79.5 | 49.0 |
| GPT-4 | Self-Correct (round 2) | 5 | 89.0 | 80.0 | 43.0 |

对照的 oracle 版本（用外部标签决定何时停止修正）：

| 模型 | 方法 | GSM8K | CommonSenseQA | HotpotQA |
|---|---|---:|---:|---:|
| GPT-3.5 | Standard Prompting | 75.9 | 75.8 | 26.0 |
| GPT-3.5 | Self-Correct (Oracle) | 84.3 | 89.7 | 29.0 |
| GPT-4 | Standard Prompting | 95.5 | 82.0 | 49.0 |
| GPT-4 | Self-Correct (Oracle) | 97.5 | 85.5 | 59.0 |

另一张表给出更弱模型的退化幅度：Llama-2 在 GSM8K 上 62.0 → 43.5（round 1）→ 36.5（round 2）；GPT-4-Turbo 91.5 → 88.0 → 90.0。

> For GSM8K, 74.7% of the time, GPT-3.5 retains its initial answer.

### 2.3 无界 agent 循环（arXiv 2607.01641）

> LLM agents increasingly rely on iterative execution to solve tasks through planning, tool use, state updates, and agent collaboration. While this design enables flexible automation, it also creates a new class of failures: an agent may repeatedly execute model calls, tools, workflow transitions, or agent handoffs when the feedback path is not effectively bounded. We call this problem Infinite Agentic Loops (IALs).

> We evaluate \toolname{} on 6,549 LLM agent repositories. It reports 74 potential findings, among which manual review confirms 68 IAL failures across 47 projects, achieving 91.9% precision.

> The corpus contains 246,748 Python files and 33.41M lines of Python code.

核心概念（本报告 §2.4 的形式化直接采用）：

> Loops are common and often legitimate in agent applications, but they become unsafe when a feedback path can repeatedly trigger costly or state-growing operations without an effective bound that constrains the controller and covers the repeated path.

> These mechanisms show that the key issue is not the presence of a loop, but whether an effective bound covers its feedback path.

> Developers may omit them, misuse them, configure them with ineffective bounds, or place them outside the actual feedback path.

### 2.4 迭代精修中的奖励攻击（arXiv 2407.04549）与自偏好放大（arXiv 2402.11436）

本报告只引用这两篇的定性机制（优化不完美代理产生的压力；多轮中自偏好被放大），不引用其具体数值，故不在此登记数值引文。

---

## 3. 人类 code review 的实证基线

### 3.1 Google（sadowski2018，ICSE-SEIP 2018）

> We find that over 80% of all changes involve at most one [iteration]

> To eventually commit a change, a developer typically must have approval from at least one reviewer. … Usually, only one reviewer is required to satisfy the aforementioned requirements of ownership and readability.

> On an average workday at Google, about 20,000 changes are committed that meet the filter criteria described above.

> Our final dataset includes the approximately 9 million changes created by more than 25,000 authors and reviewers from January 2014 until July 2016 that meet these criteria.

**注意该数据集窗口为 2014-01 至 2016-07**，即本报告引用时已距今约十年；本报告将其归类为「组织设计型结论」（§4.2 判据），其稳定性由 rigby2013 的跨组织收敛结果支持，而非由数据新鲜度支持。

### 3.2 跨组织收敛（rigby2013，ESEC/FSE 2013）

> Despite a large body of research on peer review in the software engineering literature, little … many characteristics of the review process have independently converged to similar values which we think indicate general principles of code review practice.

工具侧的一个例子说明「2 名 reviewer」曾被写成硬性业务规则：

> The CodeCollaborator tool allows for assignment of rules and the specification and enforcement of business rules (e.g., a review must be approved by 2 reviewers before it can be committed).

### 3.3 review 评论的有用率（bosu2015，MSR 2015）

> Interestingly, all projects have a similar comment usefulness density between 64% and 68%.

原文 Table 的逐项目统计（review requests / comments / useful comments / density）：

| 项目 | 领域 | Review Requests | Comments | Useful Comments | Density |
|---|---|---:|---:|---:|---:|
| Azure | Cloud software | 15,410 | 126,520 | 86,914 | 68.6% |
| Bing | Search engine | 92,987 | 664,619 | 426,513 | 64.2% |
| Visual Studio | Development tools | 12,802 | 113,208 | 75,378 | 66.6% |
| Exchange | Email server | 29,272 | 246,566 | 155,971 | 63.3% |
| Office | Office suite | 33,351 | 299,919 | 204,045 | 68.0% |
| **合计** | | **190,050** | **1,496,340** | **979,440** | **65.5%** |

> the proportion of useful comments made by a reviewer increases dramatically in the first year that he or she is at Microsoft but tends to plateau afterwards

本报告用 **65.5%（合计）** 与 **64%–68%（逐项目区间）** 作为人类 reviewer 有用率基线，用于校准对 AI reviewer 的评判尺度。

### 3.4 review 的核心难点（bacchelli2013，ICSE 2013）

> Moreover, we find that code and change understanding is the key aspect of code reviewing and that developers employ a wide range of mechanisms to meet their understanding needs, most of which are not met by current tools.

> manually inspected and classified the content of 570 comments in line discussions contained within code reviews

### 3.5 PR 评审延迟的决定因素（yu2015，MSR 2015）

> In total, we collected 103,284 pull requests from 40 different projects.

> Model 2 offers a significantly better fit (R2 = 46.1%). Pull request churn, size, and length of discussion, all highly significant, remain the most prominent predictors, together explaining 67% of the variance explained.

> the number of comments is the best single predictor of latency

> the presence of CI is a strong positive predictor

### 3.6 integrator 的工作实践（gousios2015，ICSE 2015）

> We set up an exploratory qualitative study involving a large-scale survey involving 749 integrators, to which we add quantitative data from the integrator's project.

> We conducted a two-round (pilot and main) survey with 21 and 749 respondents respectively.

> we emailed integrators from the remaining 3,150 projects and received 749 answers (23% [response rate])

> Integrators reported that explaining the reasons for rejection is one of the most challenging parts of their job as hurting the contributor's feelings is something they seek to avoid.

> Overwhelmingly, 80% of the integrators use the pull-based development model for doing code reviews and 80% to resolve issues.

---

## 9. 已撤销的引用

学术诚实要求把「查证未通过」与「查证通过」同等落盘。以下数值曾出现在本项目的早期草稿中，经全文核对后**未能在所引原文中定位**，已从正文全部移除。

### 9.1 Gousios 等 (2015) 的拒绝原因百分比

早期草稿曾写：「拒绝原因：技术质量 85%、测试失败 55%、不符合项目规范 48%」。对 `gousios2015.pdf` 全文检索 `technical quality`、`85%`、`55%`、`48%` 四项，命中数均为 **0**。该组数值可能出自同一作者群的其他文献或二手综述，但**不属于本报告所引的这一篇**，故撤销。本报告改为只引用 §3.6 中已逐字核对的部分。

### 9.2 各 agent 的总体接受率排名

早期草稿曾写：「Codex 79.9% > Cursor 74.4% > Claude Code 72.6% > Devin 68.0% = Copilot 68.0%（2025-05-19 至 07-30 共同窗口）」。arXiv 2602.08915 的摘要中，72.6% 实际是 **Claude Code 在 features 这一类任务上的接受率**，而非其总体接受率；上述五元组排名未能在摘要层面核实。撤销该排名，改为引用该文摘要中已核对的主张：**任务类型是接受率的主导因素**（documentation 82.1% vs new features 66.1%，16 个百分点的差距超过多数任务上的 agent 间方差）。

### 9.3 GPT-3.5 自我纠错的逐题翻转率

早期草稿曾写：「GPT-3.5 在 GSM8K 上只纠正了 7.6% 的错误答案，却把 8.8% 的正确答案改错」。对 `2310.01798` 源码检索 `7.6`、`8.8` 及相关措辞未能定位。撤销，改为引用 §2.2 中已逐字核对的准确率表格（GPT-3.5 GSM8K 75.9 → 75.1 → 74.7；GPT-4 95.5 → 91.5 → 89.0）。

### 9.4 IAL 论文的项目数

早期草稿曾写「68 个失败横跨 31 个项目」。原文为 **47 个项目**（`68 IAL failures across 47 projects`），且评测语料为 **6,549** 个仓库。已按原文更正。

### 9.5 IAL 六类模式的逐项占比

早期草稿曾引用一张六类失败模式的占比表（如「无界的重试反馈 25.0%」）。该表未在本次源码核对中定位到对应措辞，故正文不引用逐项占比，只引用摘要中已核对的总量（74 报告 / 68 确认 / 47 项目 / 91.9% precision）与「effective bound 是否覆盖反馈路径」这一核心判据。

### 9.6 EIR/ECR 的逐模型数值

早期草稿曾写「Opus 4.6 EIR 0.2%、ECR 25.0%；o3-mini ECR 44.1%」。本次核对只在摘要与定义处定位到 **EIR 阈值 $\lesssim 0.5\%$** 与**逐模型净收益**（o3-mini +3.4 pp、Claude Opus 4.6 +0.6 pp、o4-mini ±0 pp，GPT-5 及另四个模型退化），未定位到上述逐模型 EIR/ECR 点值。正文改用已核对的阈值与净收益。
