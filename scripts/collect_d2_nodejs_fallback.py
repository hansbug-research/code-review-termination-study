#!/usr/bin/env python3
"""D2 的降级取数路径：nodejs/node。

`scripts/collect.py` 对 nodejs/node 的 D2 查询在 8 次指数退避重试下持续返回 HTTP 502
（其余四个仓库同一查询正常）。推测原因是该仓库单页 100 个 PR 展开 labels(100) + reviews(100)
后节点数过大。本脚本用**更小的分页（25/页）与更少的嵌套字段**（reviews 30、labels 15）
取得同一批 PR 并并入 raw/d2_closed_prs.json。

对结论的影响：`reviews.totalCount` 与 `closedAt/createdAt` 均为精确值，不受嵌套上限影响；
唯一受影响的是「标签数超过 15 的 PR 可能漏检 stale 类标签」，属于对 stale 占比的**低估方向**。
该偏差方向已在 report.md §3.5 声明。

用法：
    python3 scripts/collect_d2_nodejs_fallback.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import time

RAW = pathlib.Path(__file__).resolve().parent.parent / "raw"
PAGE = 25
TARGET = 100

QUERY = """query { repository(owner:"nodejs", name:"node") {
  pullRequests(states: CLOSED, first: %d, after: %s,
               orderBy:{field: UPDATED_AT, direction: DESC}) {
    pageInfo{endCursor hasNextPage}
    nodes { number createdAt closedAt mergedAt additions deletions changedFiles
      commits{totalCount} comments{totalCount}
      labels(first:15){nodes{name}}
      reviews(first:30){totalCount nodes{state author{login}}} } } } }"""


def call(query: str, tries: int = 6) -> dict | None:
    for attempt in range(tries):
        proc = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"],
                              capture_output=True, text=True)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            if data.get("data"):
                return data["data"]
        time.sleep(min(2 ** attempt, 20))
    return None


def main() -> None:
    nodes: list[dict] = []
    cursor = "null"
    while len(nodes) < TARGET:
        data = call(QUERY % (PAGE, cursor))
        if not data:
            print(f"放弃，已取 {len(nodes)}")
            break
        conn = data["repository"]["pullRequests"]
        nodes.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = '"%s"' % conn["pageInfo"]["endCursor"]
    print(f"nodejs/node CLOSED 取得 {len(nodes)}")
    if len(nodes) < 50:
        raise SystemExit("取得数量不足 50，不并入，以免形成偏小的分母")
    path = RAW / "d2_closed_prs.json"
    payload = json.loads(path.read_text())
    payload["nodejs/node"] = nodes[:TARGET]
    path.write_text(json.dumps(payload, ensure_ascii=False))
    print(f"已并入 d2，仓库数 {len(payload)}")


if __name__ == "__main__":
    main()
