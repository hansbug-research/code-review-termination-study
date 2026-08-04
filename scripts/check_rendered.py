#!/usr/bin/env python3
"""抓取 GitHub 上已发布的 Markdown 渲染结果，核对它与源码的意图是否一致。

与 check_math.py 的分工。`check_math.py` 是**静态**检查，规则确定、可离线跑、进 CI；但它
的六条规则**全部是从这里的实测结果反推出来的**——E6（公式内的 `*`）就是在前五条修完、
重新抓渲染结果时才暴露的。静态规则只能挡住已知的失效类别，新类别只能靠看真实渲染结果发现。
因此这个脚本是发布后的核对工具，不进 CI（CI 跑的时候当前提交往往还没被 GitHub 渲染）。

核对四件事：

  1. 漏渲染的公式——源码写了 `$...$`，网页上却以字面量出现（说明未被识别为数学）
  2. 公式碎片——渲染结果里出现含反斜杠的 `<em>`，说明 Markdown 的强调解析吃掉了公式
  3. 表格错位——某一行的单元格数与表头不一致
  4. 图片失效——`<img>` 的目标取不回来或体积异常小

用法：
    python3 scripts/check_rendered.py                       # 核对仓库内全部 Markdown
    python3 scripts/check_rendered.py report.md             # 只核对指定文件
    python3 scripts/check_rendered.py --ref <sha> report.md # 核对指定提交
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLUG = "hansbug-research/code-review-termination-study"
SKIP_DIRS = {".git", "raw", "derived", "figures", "__pycache__"}


def curl(url: str, args: list[str] | None = None) -> str:
    return subprocess.run(["curl", "-s", "--max-time", "60", *(args or []), url],
                          capture_output=True, text=True).stdout


def rendered_html(path: str, ref: str) -> str | None:
    """取回 blob 页并还原其中的渲染结果（GitHub 把它作为 JSON 字符串嵌在页面里）。"""
    page = curl(f"https://github.com/{SLUG}/blob/{ref}/{path}")
    key = '"richText":"'
    if key not in page:
        return None
    seg = page[page.find(key) + len(key):]
    buf, i = [], 0
    while i < len(seg):
        c = seg[i]
        if c == "\\":
            buf.append(seg[i:i + 2])
            i += 2
            continue
        if c == '"':
            break
        buf.append(c)
        i += 1
    return json.loads('"' + "".join(buf) + '"')


def check(path: str, body: str) -> list[str]:
    bad: list[str] = []
    n_math = len(re.findall(r"<math-renderer", body))

    # 1) 漏渲染的公式：剥掉代码与已渲染的公式后，正文里不应再出现成对的 `$`
    stripped = re.sub(r"<pre.*?</pre>", "", body, flags=re.S)
    stripped = re.sub(r"<code.*?</code>", "", stripped, flags=re.S)
    stripped = re.sub(r"<math-renderer.*?</math-renderer>", "", stripped, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", "", stripped))
    for m in re.finditer(r"\$([^$\n]{1,80})\$", text):
        bad.append(f"漏渲染的公式：{m.group(0)[:70]!r}")

    # 2) 公式碎片：含反斜杠的 <em> 只可能来自被强调解析吃掉的 LaTeX
    for e in re.findall(r"<em>(.*?)</em>", body, re.S):
        if "\\" in e:
            bad.append(f"公式被解析成强调：{html.unescape(e)[:70]!r}")

    # 3) 表格错位
    for i, t in enumerate(re.findall(r"<table>(.*?)</table>", body, re.S), 1):
        ths = len(re.findall(r"<th[ >]", t))
        rows = [len(re.findall(r"<td[ >]", r))
                for r in re.findall(r"<tr>(.*?)</tr>", t, re.S)[1:]]
        if rows and set(rows) != {ths}:
            bad.append(f"第 {i} 张表列数不一致：表头 {ths}，数据行 {sorted(set(rows))}")

    # 4) 图片
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', body)
    for src in imgs:
        url = "https://github.com" + src if src.startswith("/") else src
        r = curl(url, ["-L", "-o", "/dev/null", "-w", "%{http_code} %{size_download}"])
        code, size = (r.split() + ["0", "0"])[:2]
        if code != "200" or int(size) < 5000:
            bad.append(f"图片异常（HTTP {code}，{size} 字节）：{src}")

    print(f"{path}: 公式 {n_math} 个 · 表格 {len(re.findall(r'<table>', body))} 张 · "
          f"图片 {len(imgs)} 张 · 问题 {len(bad)} 处")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--ref", default="main")
    args = ap.parse_args()

    # 跳过符号链接：GitHub 的网页**不渲染**符号链接（`AGENTS.md` 在网页上显示为一条指向
    # `CLAUDE.md` 的链接条目，而不是 Markdown 正文），取不到 richText 属于预期而非问题。
    paths = args.paths or [str(p.relative_to(ROOT)) for p in sorted(ROOT.rglob("*.md"))
                           if not any(x in p.parts for x in SKIP_DIRS)
                           and not p.is_symlink()]
    total = 0
    for path in paths:
        body = rendered_html(path, args.ref)
        if body is None:
            print(f"{path}: 取不到渲染结果（未推送？路径不对？）")
            total += 1
            continue
        for problem in check(path, body):
            total += 1
            print(f"    !! {problem}")
    print(f"\n{len(paths)} 个文件，共 {total} 处渲染问题")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
