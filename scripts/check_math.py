#!/usr/bin/env python3
"""扫描仓库内所有 Markdown 中的行内与行间公式，检出在 GitHub 上会渲染错误的写法。

为什么需要它。GitHub 的渲染管线**先做 Markdown 的反斜杠转义，再把 `$...$` 交给 MathJax**。
CommonMark 允许反斜杠转义任意 ASCII 标点，因此 `\\{`、`\\%`、`\\_`、`\\&`、`\\#` 这些在 LaTeX 里
完全正常的写法，会在到达 MathJax 之前被吃掉一层反斜杠，公式随之变成另一个意思——甚至静默
失效。本仓库首版实际踩了 18 处（逐条清单见 audit/math_render_audit.md），且全部是「本地看着
没问题、网页上错了」，人眼不可靠，所以做成检查项。

检出的六类问题：

  E1 反斜杠 + ASCII 标点   `$\\{a,b\\}$` → Markdown 先转义成 `${a,b}$`，花括号变成分组符而不显示；
                          `$0.5\\%$` → 变成 `$0.5%$`，`%` 在 TeX 里是注释符，其后内容全部消失。
                          表格单元格内的 `\\|` 是例外：GFM 用它表示字面竖线，转义后正是所需的 `|`。
  E2 公式内的 CJK          MathJax 的字体不含 CJK 字形，`\\text{中文}` 的渲染依赖浏览器回退，
                          结果不可控。中文一律留在公式外。
  E3 `$$` 未独占一行        行间公式的定界符与内容同行时，GitHub 有时不识别为公式块。
  E4 单行内 `$` 数目为奇数   通常意味着漏了定界符，或把货币符号写成了未转义的 `$`。
  E5 开定界符紧跟中文标点  GitHub 只在开定界符 `$` 前是空格、行首或 ASCII 标点时才识别行内公式。
                          写成「空间，$F$ 为…」时，`$F$` 会原样输出为字面量而不是公式——这一条
                          是实测出来的：本仓库首版有 12 处这种写法，网页上全部漏渲染，而本地
                          Markdown 预览器多半照常显示，因此只能靠检查项守住。改法是在中文标点
                          与 `$` 之间加一个半角空格。
  E6 公式内的 `*`          星号会被 Markdown 的强调解析先行消费，把公式拆成 `<em>` 而不是数学。
                          `_` 因为有「词内下划线不构成强调」的规则而幸免，`*` 没有这条豁免。
                          改法：上标星号写 `^{\ast}`，二元运算符写 `\ast` 或 `\star`。

用法：
    python3 scripts/check_math.py            # 有问题则退出码 1
    python3 scripts/check_math.py --list     # 列出全部公式，供人工过目
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "raw", "derived", "figures", "__pycache__"}

# CommonMark 允许被反斜杠转义的 ASCII 标点全集。公式内出现 `\` + 其中任一字符即为 E1。
ESCAPABLE = set("""!"#$%&'()*+,-./:;<=>?@[]^_`{|}~\\""")
CJK = re.compile(r"[㐀-鿿　-〿＀-￯]")
INLINE = re.compile(r"(?<!\$)\$(?!\$)((?:[^$\n]|\\\$)+?)(?<!\\)\$(?!\$)")
DISPLAY = re.compile(r"\$\$(.+?)\$\$", re.S)


def md_files() -> list[Path]:
    """仓库内的 Markdown 文件。跳过符号链接：`AGENTS.md` 指向 `CLAUDE.md`，
    跟进去只会把同一份内容扫两遍。"""
    return sorted(p for p in ROOT.rglob("*.md")
                  if not any(part in SKIP_DIRS for part in p.parts)
                  and not p.is_symlink())


def in_code_block(lines: list[str], idx: int) -> bool:
    """判断第 idx 行是否位于围栏代码块内（代码块里的 `$` 不参与数学解析）。"""
    fence = 0
    for l in lines[:idx]:
        if l.lstrip().startswith(("```", "~~~")):
            fence += 1
    return fence % 2 == 1


def mask_code(line: str) -> str:
    """把行内代码段的内容替换成等长空格。

    反引号里的 `$0.5\\%$` 是**在讲**一种写法，不是在用它；不屏蔽的话，本检查项会把自己的
    说明文档判成违规。用等长空格而非删除，是为了让 E5 依赖的字符偏移保持有效。
    """
    return re.sub(r"`+[^`]*`+", lambda m: " " * len(m.group(0)), line)


def scan(path: Path) -> list[tuple[str, int, str, str]]:
    text = path.read_text(encoding="utf-8")
    raw = text.split("\n")
    # 屏蔽围栏代码块与行内代码段后再解析：两者里的 `$` 都不参与数学解析
    lines = [" " * len(l) if in_code_block(raw, i) else mask_code(l)
             for i, l in enumerate(raw)]
    text = "\n".join(lines)
    out: list[tuple[str, int, str, str]] = []

    # ---- E3 / E4：逐行检查定界符本身
    for i, line in enumerate(lines, 1):
        # 去掉引用块前缀后再判断：`> $$` 与 `$$` 是等价的合法写法
        stripped = re.sub(r"^[>\s]+", "", line).strip()
        if "$$" in line and stripped != "$$":
            out.append(("E3", i, line.strip()[:90], "`$$` 未独占一行"))
        if "$$" not in line:
            n = len(re.findall(r"(?<!\\)\$", line))
            if n % 2:
                out.append(("E4", i, line.strip()[:90], f"单行内未转义的 `$` 有 {n} 个（奇数）"))

    # ---- E1 / E2：检查公式内容
    def check(body: str, line_no: int, kind: str) -> None:
        row_is_table = raw[line_no - 1].lstrip().startswith("|")
        for m in re.finditer(r"\\(.)", body):
            ch = m.group(1)
            if ch not in ESCAPABLE:
                continue
            if ch == "|" and row_is_table:
                continue          # GFM 表格里 `\|` 转义后正好得到所需的 `|`
            out.append(("E1", line_no, body.strip()[:90],
                        f"公式内 `\\{ch}` 会被 Markdown 先行转义（{kind}）"))
        if CJK.search(body):
            out.append(("E2", line_no, body.strip()[:90], f"公式内含 CJK 字符（{kind}）"))
        if "*" in body:
            out.append(("E6", line_no, body.strip()[:90],
                        f"公式内的 `*` 会被 Markdown 的强调解析吃掉（{kind}），改用 `\\ast`"))

    for m in DISPLAY.finditer(text):
        check(m.group(1), text[:m.start()].count("\n") + 1, "行间")
    for i, line in enumerate(lines, 1):
        if "$$" in line:
            continue
        for m in INLINE.finditer(line):
            check(m.group(1), i, "行内")
            prev = line[m.start() - 1] if m.start() else ""
            if prev and (ord(prev) > 127) and not prev.isspace():
                out.append(("E5", i, f"{prev}${m.group(1)[:40]}$",
                            f"开定界符前紧跟非 ASCII 字符 `{prev}`，GitHub 不会识别为公式"))
    return out


def main() -> int:
    if "--list" in sys.argv:
        for p in md_files():
            raw = p.read_text(encoding="utf-8").split("\n")
            lines = [" " * len(l) if in_code_block(raw, i) else mask_code(l)
                     for i, l in enumerate(raw)]
            for m in DISPLAY.finditer("\n".join(lines)):
                print(f"{p.relative_to(ROOT)}  [行间] {m.group(1).strip()[:100]}")
            for i, line in enumerate(lines, 1):
                if "$$" in line:
                    continue
                for m in INLINE.finditer(line):
                    print(f"{p.relative_to(ROOT)}:{i}  [行内] {raw[i-1][m.start():m.end()][:100]}")
        return 0

    total = 0
    for p in md_files():
        for code, line, snippet, why in scan(p):
            total += 1
            print(f"{code}  {p.relative_to(ROOT)}:{line}  {why}\n      {snippet}")
    if total:
        print(f"\n共 {total} 处公式写法问题")
        return 1
    print(f"{len(md_files())} 个 Markdown 文件的公式写法检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
