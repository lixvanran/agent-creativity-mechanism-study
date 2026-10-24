#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 「离线落盘向量」与「在线通道」算出的读数【逐位等值】的验证 ★

> 落点：`creativity_lab/experiments/verify_offline_equivalence.py`
> 用法：
>   python3 -B creativity_lab/experiments/verify_offline_equivalence.py \
>       --out runs/topo-arm-v2-2026-10-24 \
>       --unit-list docs/交付/读数快照/topo-arm-v2-n151/UNITS-n151.txt \
>       --vectors-dir docs/交付/读数快照/topo-arm-v2-n151/vectors
> 退出码：0 = 逐位等值（★ 离线可算已被证明 ★）；1 = 不等；2 = 跑不动
>
> ★ ★★ 为什么要有这个（★ 2026-10-24 ★）★★
★ 「有落盘向量就不用再调嵌入」★ 这句话本身**只是设计意图** ★ ⇒ ★ **必须证明【落盘向量算出来的读数】与【通道现算的读数】逐位相同** ★
★ ⇒ ★ **否则「离线可算」只是【看起来】能用，★ 而复核者无法判断它是否等价** ★
★ ⇒ ★ ★ **⇒ 这就是「我方说能用」与「我方证明能用」的区别 ★★ ★
>
> ★ ★★ 判据 ★★
★ | 项 | 口径 |
★ |:-:|---|
| ★ 比对对象 | ★ 每个 (题, rep, 臂) 组的 **Vendi 分数** ★ |
| ★ 容差 | ★ **0（逐位）** ⇒ ★ 不容差 ★ |
| ★ 不等时 | ★ **响亮失败**（★ exit 1 ★）+ 打印差值最大的组 ★ |
| ★ 通道不可用 | ★ **exit 2**（★ 不静默跳过 ★）★ |
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--unit-list", required=True)
    ap.add_argument("--vectors-dir", required=True)
    ap.add_argument("--runs-per-arm", type=int, default=5)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    from creativity_lab.experiments.partial_verdict import read_set  # ★ 复用同一套读数口径 ★

    units = [ln.strip() for ln in open(a.unit_list, encoding="utf-8") if ln.strip()]
    # ── ① 落盘向量 → 文本映射 ──
    # ★ ★ 用【client.embed 的缓存路径算法】反查（★ 与 embed 实际用法【完全一致】★★
    #   ★ ⇒ ★ 不自己发明目录格式（★ 上一版就栽在这儿：★ vectors/ 按 unit_id、
    #   ★ vector_cache/ 按文本 sha256 ⇒ ★ 两个目录形态不同 ⇒ ★ 查不到 ★）★★
    from creativity_lab.client import _cache_path
    vmap = {}
    _n_units = 0
    for fn in sorted(os.listdir(os.path.join(a.out, "units"))):
        if not fn.endswith(".json"):
            continue
        _uid = fn[:-5]
        _up = os.path.join(a.out, "units", fn)
        try:
            u = json.load(open(_up, encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            continue
        p = u.get("post")
        if not isinstance(p, str) or not p.strip():
            continue
        _cp = _cache_path(a.vectors_dir, p, "db")
        if not os.path.isfile(_cp):
            continue
        try:
            o = json.load(open(_cp, encoding="utf-8"))
            if o.get("vector"):
                vmap.setdefault(p, o["vector"])
                _n_units += 1
        except Exception:                                        # noqa: BLE001
            continue
    print("== ★ 离线 ≡ 在线 等值性验证（★ 2026-10-24 ★）==")
    print("   落盘向量文本数：%d（★ 来自单元文件 %d 个 ★）" % (len(vmap), _n_units))
    if not vmap:
        print("   ✘ 没有落盘向量 ⇒ 退出码 2")
        return 2

    # ── ② 组装满组（★ **直接复用 partial_verdict 的 load_groups** ★）──
    #   ★ ★ 为何复用：★ 单元 id 的解析必须与主分析【同口径】⇒ ★
    #   ★ ★ 臂名含下划线（★ nosel_b3_synth ★）⇒ ★ 自己 split 会切错 ★★ ⇒ ★ 不自己写 ★
    from creativity_lab.experiments.partial_verdict import load_groups
    _g = load_groups(os.path.join(a.out, "units"), allowed=set(units))
    full = {k: v for k, v in _g.items() if len(v) == a.runs_per_arm}
    print("   满组（%d 份）：%d 组" % (a.runs_per_arm, len(full)))
    if not full:
        print("   ✘ 没有满组 ⇒ 退出码 2")
        return 2

    # ── ③ 离线读数 ──
    off = {}
    for k, arts in sorted(full.items()):
        off[k] = read_set(arts, [vmap[t] for t in arts])

    # ── ④ 在线读数（★ 通道不可用 ⇒ exit 2，★ 不静默跳过 ★）──
    from creativity_lab.client import LLM
    texts = []
    for k, arts in sorted(full.items()):
        for t in arts:
            if t not in texts:
                texts.append(t)
    try:
        vecs = LLM().embed(texts)
    except Exception as e:                                      # noqa: BLE001
        print("   ✘ 嵌入通道不可用：%s ⇒ 退出码 2（★ 不静默跳过 ★）" % e)
        return 2
    live = {t: v for t, v in zip(texts, vecs)}
    on = {}
    for k, arts in sorted(full.items()):
        on[k] = read_set(arts, [live[t] for t in arts])

    # ── ⑤ 逐位比对 ──
    bad = []
    worst = 0.0
    for k in sorted(off):
        o1, o2 = off[k], on[k]
        for m in ("vendi", "modes", "structured_dedup_count"):
            d = abs(float(o1.get(m, 0)) - float(o2.get(m, 0)))
            worst = max(worst, d)
            if d != 0.0:
                bad.append((k, m, o1.get(m), o2.get(m), d))
    print("   比对 %d 组 × 3 个读数 ｜ 最大绝对差 = %r" % (len(off), worst))
    if bad:
        print("   ✘✘ 离线与在线【不等】（★ 逐位、★ 容差 0 ★）：")
        for k, m, x, y, d in bad[:10]:
            print("     - %s %s：离线 %r vs 在线 %r（Δ=%r）" % (k, m, x, y, d))
        return 1
    print("   ✔✔ 逐位等值（★ Δ = 0 ⇒ ★ **「离线可算」已被证明** ★）")
    if a.json_out:
        import datetime as _dt
        with open(a.json_out, "w", encoding="utf-8") as _f:
            json.dump({"checked_at_utc": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "n_groups": len(off), "metrics": ["vendi", "modes", "structured_dedup_count"],
                       "max_abs_diff": worst, "equivalent": True,
                       "vectors_dir": a.vectors_dir,
                       "note": "★ 落盘向量算出的读数与通道现算【逐位相同】⇒ ★ 此后不再依赖嵌入通道 ★"},
                      _f, ensure_ascii=False, indent=1, sort_keys=True)
        print("   ✔ 落盘 %s" % a.json_out)
    print("   ⇒ ★ 此后 Vendi 与任何谱统计量【不再依赖嵌入通道存续】★")
    return 0


if __name__ == "__main__":
    sys.exit(main())
