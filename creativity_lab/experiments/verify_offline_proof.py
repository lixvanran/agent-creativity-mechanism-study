#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 断网证明：★ 把「离线」从【声称】变成【证据】★★

★ ★★ 为什么必须有这个脚本（★ 纪律）★★
★ 「离线优先」做完后，★ 「离线」与「**声称离线**」在输出层【完全同形】——
★   ★ 两者都能跑出【完全正确】的读数 ★ ⇒ ⇒ ★ 除非额外取证，★ 否则无法区分 ★
★ ⇒ ★★ 唯一可靠的区分方式：★ ★【把通道端【故意搞坏】，★ 再跑一遍】★★ ★
★   ★ 若【通道端坏了仍能跑完】⇒ ★ 它根本没走网络（★ 走的是缓存 ★）
★   ★ 配套的【负对照】：★ 【通道端坏了 + 无缓存 ⇒ 必须失败】★★
★   ★ ★ 这一对【正+负】才是完整证明（★ 只做正对照 ⇒ 可能是「代码压根不调通道」★
★   ★   ——★ 那也说明缓存生效，★ 但没证明【通道端真的坏了】★）★★★ ★

★ 两条硬要求：
★   ① 坏 key 不得影响【正在跑的批】⇒ ★ 用【子进程 env 覆盖】★ 不改全局环境 ★
★   ② 输出必须【可重算】⇒ ★ 落盘 json 里【每个数都来自本次运行】★ 不得硬编码 ★
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BAD_KEY = "wrong-key-for-negative-test"

NEG_SNIPPET = r"""
import sys, json
sys.path.insert(0, %r)
from creativity_lab.client import LLM
try:
    v = LLM().embed(["offline proof negative control"])
    print(json.dumps({"ok": True, "dim": len(v[0]) if v else 0}))
except Exception as e:
    print(json.dumps({"ok": False, "err": type(e).__name__, "msg": str(e)[:160]}))
"""


def die(msg):
    print("✘ %s" % msg)
    sys.exit(1)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="★ run-dir（★ 单元文件所在 ★）")
    ap.add_argument("--unit-list", required=True, help="★ 单元清单（★ 冻结的那一份 ★）")
    ap.add_argument("--cache-dir", required=True, help="★ 向量缓存目录（★ 须非空 ★）")
    ap.add_argument("--json-out", required=True)
    ap.add_argument("--online-json", required=True,
                    help="★ 在线版读数（★ 逐位对照的基准 ★）")
    a = ap.parse_args()

    if not os.path.isdir(a.cache_dir):
        die("cache-dir 不存在：%s" % a.cache_dir)
    # ★ ★ 缓存是【两级】目录（★ client._cache_path：★ k[:2]/k.json ★）⇒ ★ 必须【递归】数 ★
    #   ★ 只看顶层 ⇒ ★ 会把「151 个缓存文件」判成【空】⇒ ★ ★ 又一次「目录形态与实际调用方式不一致」★★
    _n_cache = 0
    for _r, _d, _fs in os.walk(a.cache_dir):
        _n_cache += len([f for f in _fs if f.endswith(".json")])
    if _n_cache == 0:
        die("cache-dir 为空：%s（★ 空缓存 ⇒ 证明不成立 ★）" % a.cache_dir)

    # ★ 负对照：★ 坏 key + 【无缓存】⇒ 必须失败 ★
    env = dict(os.environ)
    env.pop("MM_VECTOR_CACHE_DIR", None)
    env["MINIMAX_SUBSCRIPTION_KEY"] = BAD_KEY
    r = subprocess.run([sys.executable, "-B", "-c", NEG_SNIPPET % ROOT],
                       capture_output=True, text=True, env=env, timeout=300)
    neg_ok = False
    neg_err = ""
    for line in reversed([l for l in r.stdout.split("\n") if l.strip()]):
        try:
            o = json.loads(line)
            neg_ok = not bool(o.get("ok"))
            neg_err = "%s: %s" % (o.get("err", "?"), o.get("msg", ""))
            break
        except Exception:                                        # noqa: BLE001
            continue
    print("① 负对照（★ 坏 key + 无缓存 ★）：%s" % ("✔ 按预期失败" if neg_ok else "✘ 未失败"))
    if not neg_ok:
        die("负对照未失败 ⇒ ★ 「通道端坏了」这个前提不成立 ⇒ ★ 整套证明不成立 ★")

    # ★ 正对照：★ 坏 key + 【有缓存】⇒ 必须跑完 ★
    env2 = dict(os.environ)
    env2["MINIMAX_SUBSCRIPTION_KEY"] = BAD_KEY
    env2["MM_VECTOR_CACHE_DIR"] = a.cache_dir
    out_json = a.json_out + ".offline_run.json"
    cmd = [sys.executable, "-B", os.path.join(HERE, "partial_verdict.py"),
           "--out", a.out, "--unit-list", a.unit_list, "--json-out", out_json]
    r2 = subprocess.run(cmd, capture_output=True, text=True, env=env2, timeout=3600)
    if r2.returncode != 0:
        die("正对照跑失败（exit=%s）：%s" % (r2.returncode, (r2.stderr or "")[-400:]))
    print("② 正对照（★ 坏 key + 有缓存 ★）：✔ 跑完")

    # ★ 逐位对照 ★
    if not os.path.isfile(a.online_json):
        die("online-json 不存在：%s" % a.online_json)
    off = json.load(open(out_json, encoding="utf-8"))
    on = json.load(open(a.online_json, encoding="utf-8"))
    keys = sorted(set(off) | set(on))
    diff = [k for k in keys if off.get(k) != on.get(k)]
    print("③ 逐位对照：★ 顶层键 %d 个 ｜ **不同 %d 个** %s"
          % (len(keys), len(diff), ("⇒ " + ", ".join(diff[:8])) if diff else ""))
    if diff:
        die("逐位对照不一致 ⇒ ★ 离线读数与在线读数【不是同一份】★")

    out = {
        "checked_at_utc": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"),
        "proof": "offline_proof_by_wrong_key",
        "cache_dir": a.cache_dir,
        "n_cache_files": _n_cache,
        "negative_control": {"scenario": "★ 坏 key + 【无缓存】⇒ 通道拒绝 ★",
                             "passed": neg_ok, "err": neg_err},
        "positive": {"scenario": "★ 坏 key + 【有缓存】⇒ 跑完且逐位一致 ★",
                     "passed": True,
                     "theta0": off.get("theta0"),
                     "n_units_actual": off.get("n_units_actual")},
        "top_level_keys_compared": len(keys),
        "keys_differing": len(diff),
        "keys_differing_list": diff,
        "online_sha256": sha256_of(a.online_json),
        "note": "★ 「离线」不能只是声称：★ 坏 key 下仍能跑完 ⇒ ★ 它根本没走网络；★ "
                "而坏 key + 无缓存【确实失败】⇒ ★ 前后照成立 ★",
    }
    tmp = a.json_out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, a.json_out)
    try:
        os.remove(out_json)
    except OSError:
        pass
    print("✔ 落盘 %s ｜ sha256 %s" % (a.json_out, sha256_of(a.json_out)[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
