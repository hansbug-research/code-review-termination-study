# AGENTS.md

本仓库的通用工作约定见 [`CLAUDE.md`](CLAUDE.md)，评审规则见 [`REVIEW.md`](REVIEW.md)。二者对所有 agent 同等适用。

提交前必须全绿：

```bash
python3 scripts/analyze.py && python3 scripts/plot.py \
  && python3 scripts/gen_references.py && python3 scripts/verify.py
```

## Code Review Rules

### 证据链

- 正文中出现了未登记在 `derived/stats.json` 中的统计量。
  Safe path：先在 `scripts/analyze.py` 里算出并落盘，再在 `scripts/verify.py` 里加断言；只有这样的数字才能写进正文。

- 引用文献数值时未在 `lit/quotes.md` 中登记原文。
  Safe path：登记逐字原文并注明小节；确实定位不到的，写进该文件 §9「已撤销的引用」并从正文移除。

- 修改了 `raw/` 下的任何文件。
  Safe path：`raw/` 是 API 原始响应，只增不改；数据有问题就新增采集脚本并在 `report.md` §3.3 记录原因。

### 引用

- 手写参考文献著录信息，或手改 `gen_references.py` 生成的编号。
  Safe path：著录信息只能来自 `lit/references.json`（由 arXiv / DBLP 接口取回）；改动后重跑 `scripts/gen_references.py` 回填。

- 正文引用只写编号而不带 key（如写成 `[18]` 而非 `[[18]](#ref-sadowski2018)`）。
  Safe path：始终带 key，否则「编号 ↔ 文献」的映射无法被机器核对。

### 结论强度

- 把区间上界或下界当作点估计陈述。
  Safe path：明确写出它是上界还是下界，并说明偏差方向的成因。

- 用聚簇样本做跨组比较而未做稳健性诊断。
  Safe path：给出留一刀切区间与仓库级宏平均；若刀切区间跨度过大，声明该比较不成立而不是取中间值。

### 写作

- 自然段内出现硬换行。
  Safe path：一个自然段一行长句；表格、代码块、列表不受此限。

- 图表标题描述图形而非结论（如「XX 分布图」）。
  Safe path：标题写这张图支持的那句结论。

格式化、拼写、lint 一类的机械检查留在 CI，不要写成评审规则。
