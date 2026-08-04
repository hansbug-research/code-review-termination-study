#!/usr/bin/env python3
"""D8 补充采集：为 D1 的 500 个已合并 PR 逐个取回作者身份。

动机（测量效度）。D1 用 `reviews.totalCount == 0` 定义「零正式 review」，但该计数只统计
GitHub 的 review 对象。若项目用机器人指令（Prow 的 `/lgtm`、`/approve`）或自动化回合（bors
rollup、自动 backport）完成批准，批准事实不会体现在该计数里，于是「零正式 review」会同时
混入两类完全不同的对象：真正无人过目的 PR，以及经由非 review 通道批准的 PR。二者对本研究
的结论方向相反，必须分离。作者身份是分离它们的最低成本判据——自动 backport 与 rollup 由
机器人发起，人类提交的补丁则不然。

实现上按 PR 号精确取回（而非重跑 search），以保证与 D1 完全同一批对象；每批 25 个别名查询。

用法：
    python3 scripts/collect_d8_authors.py
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
BATCH = 25


def gh_graphql(query: str, tries: int = 6, label: str = "") -> dict:
    last = ""
    for attempt in range(tries):
        p = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"],
                           capture_output=True, text=True)
        if p.returncode == 0:
            return json.loads(p.stdout)["data"]
        last = p.stderr.strip()
        time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"GraphQL 失败（{label}），最后一次错误：{last}")


def fetch(owner: str, name: str, numbers: list[int]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for i in range(0, len(numbers), BATCH):
        chunk = numbers[i:i + BATCH]
        parts = "\n".join(
            f'p{n}: pullRequest(number: {n}) {{ number author {{ login __typename }} '
            f'authorAssociation }}' for n in chunk)
        q = f'{{ repository(owner: "{owner}", name: "{name}") {{ {parts} }} }}'
        data = gh_graphql(q, label=f"d8:{owner}/{name}:{i}")
        for v in (data["repository"] or {}).values():
            if v:
                out[v["number"]] = {
                    "author": (v["author"] or {}).get("login"),
                    "author_type": (v["author"] or {}).get("__typename"),
                    "author_association": v["authorAssociation"],
                }
        print(f"  {owner}/{name}: {len(out)}/{len(numbers)}", flush=True)
    return out


def main() -> None:
    d1 = json.loads((RAW / "d1_merged_prs.json").read_text())
    result: dict[str, dict] = {}
    for repo, prs in d1.items():
        owner, name = repo.split("/")
        numbers = [p["number"] for p in prs if p.get("mergedAt")]
        result[repo] = {str(k): v for k, v in fetch(owner, name, numbers).items()}
    (RAW / "d8_d1_authors.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1))
    print(f"写入 raw/d8_d1_authors.json：{sum(len(v) for v in result.values())} 个 PR")


if __name__ == "__main__":
    main()
