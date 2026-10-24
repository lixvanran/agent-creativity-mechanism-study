#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cmp8_fetch.py —— 把交付包从 drive 拉下来（本地没有 mavis CLI 也能用）。

用法：
    python3 cmp8_fetch.py --node-id 454375285564150     # 按 drive node_id 拉（需本机有 mavis CLI）
    python3 cmp8_fetch.py --url "<签名下载链接>"          # 直接用签名链接（最通用）
    python3 cmp8_fetch.py --local ./cmp8_交付包.zip       # 校验一个已有的本地包

说明：
- `--url` 不需要任何凭据，签名链接有时效（通常 1 小时），过期了就重新从
  Mavis 文件管理界面取一次。
- `--node-id` 会在本机找 `mavis` CLI（`mavis drive files download --node_id=...`）拿到签名链接；
  找不到 CLI 就直接告诉你下一步怎么办，不会瞎猜。
- 本脚本**不碰任何 key**，只做下载与校验。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request

DEFAULT_NAME = "cmp8_交付包.zip"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def from_url(url: str, dest: str) -> str:
    print("下载：%s" % url[:120] + ("…" if len(url) > 120 else ""))
    req = urllib.request.Request(url, headers={"User-Agent": "cmp8-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    return dest


def from_node(node_id: str, dest: str) -> str:
    cli = shutil.which("mavis")
    if not cli:
        raise SystemExit(
            "✗ 本机没有 mavis CLI，无法按 node_id 取签名链接。\n"
            "  下一步（二选一）：\n"
            "   1) 在 Mavis 文件管理界面打开这个 node，复制它的下载链接，然后：\n"
            "      python3 cmp8_fetch.py --url \"<签名下载链接>\"\n"
            "   2) 或者把 zip 手动下下来，然后：\n"
            "      python3 cmp8_fetch.py --local ./%s" % DEFAULT_NAME)
    print("用 mavis CLI 取签名链接：node_id=%s" % node_id)
    out = subprocess.run([cli, "drive", "files", "download", "--node_id", node_id],
                         capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise SystemExit("✗ mavis CLI 失败：%s" % (out.stderr or out.stdout)[:300])
    txt = out.stdout
    url = ""
    for key in ("download_url", "url", "cdn_url"):
        idx = txt.find('"%s"' % key)
        if idx >= 0:
            seg = txt[idx:]
            a = seg.find(":") + 1
            b = seg.find('"', a)
            if b > a:
                url = seg[a:b]
                break
    if not url:
        raise SystemExit("✗ 没能从 mavis 输出里解析出下载链接：%s" % txt[:300])
    return from_url(url, dest)


def verify(path: str) -> None:
    print("\n=== 校验 ===")
    print("路径: %s" % os.path.abspath(path))
    print("字节: %d" % os.path.getsize(path))
    print("sha256: %s" % sha256(path))
    try:
        import zipfile
        z = zipfile.ZipFile(path)
        bad = z.testzip()
        names = z.namelist()
        print("zip 内条目: %d" % len(names))
        print("完整性: %s" % ("OK（无坏文件）" if bad is None else "坏文件: %s" % bad))
        need = ["cmp8pkg/README.md", "cmp8pkg/METHOD.md", "cmp8pkg/AGENT_RUNBOOK.md",
                "cmp8pkg/run_compare5.py", "cmp8pkg/analyze_cmp6.py",
                "cmp8pkg/creativity_lab/orclient.py", "cmp8pkg/armdeps/topics4.py",
                "cmp8pkg/runs/arch_learn/result.json"]
        miss = [n for n in need if n not in names]
        print("关键文件: %s" % ("全在 ✔" if not miss else "缺: %s" % miss))
        print("\n下一步：unzip -q %s && cd cmp8pkg && bash rebuild/rebuild.sh" % os.path.basename(path))
    except Exception as e:
        print("⚠ zip 校验异常: %s" % str(e)[:200])


def main() -> int:
    ap = argparse.ArgumentParser(description="把 cmp8 交付包从 drive 拉下来")
    ap.add_argument("--node-id", default="", help="drive node_id（需本机有 mavis CLI）")
    ap.add_argument("--url", default="", help="签名下载链接")
    ap.add_argument("--local", default="", help="已在本地的包路径（只做校验）")
    ap.add_argument("--out", default=DEFAULT_NAME, help="保存文件名")
    a = ap.parse_args()

    if a.local:
        if not os.path.exists(a.local):
            raise SystemExit("✗ 文件不存在: %s" % a.local)
        verify(a.local)
        return 0

    dest = a.out
    if a.url:
        from_url(a.url, dest)
    elif a.node_id:
        from_node(a.node_id, dest)
    else:
        ap.print_help()
        print("\n（三个参数至少给一个）")
        return 2

    verify(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
