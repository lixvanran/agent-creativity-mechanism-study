#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 【事后补录】per-unit 原始向量：★ 一次充值 ⇒ 此后永久离线可算 ★

> 落点：`creativity_lab/experiments/backfill_vectors.py`
> 用法：
>   # ① 先干跑（★ 零消耗 · ★ 现在就能跑 ★）
>   python3 -B creativity_lab/experiments/backfill_vectors.py \
>       --run-dir runs/topo-arm-v2-2026-10-25 \
>       --unit-list docs/交付/读数快照/topo-arm-v2-n151/UNITS-n151.txt \
>       --out-dir docs/交付/读数快照/topo-arm-v2-n151/vectors --dry-run
>   # ② 充值后真跑（★ 调嵌入通道 · ★ 落盘原始向量 ★）
>   python3 -B creativity_lab/experiments/backfill_vectors.py ... （去掉 --dry-run）
>
> ★ ★★ 为什么要有这个（★ 2026-10-26 · 第 1 层论证线的可抄思路 ★）★★
★ ★ **★ 「被测量的那个量，★ 在【生成时】就已经算好并落盘了」⇒ ★ 事后分析只是重算统计量
★ ★ ⇒ ★ 【复核、★ 分析、★ 重算全部不再依赖付费通道的存续】★★ ★
★ ⇒ ★ **落到 Vendi**：★ 谱熵需要每条产出的向量 ⇒ ★ 只要把 per-unit 向量落盘 ⇒ ★
★ ★ Vendi 与任何谱统计量都【只需这些向量】⇒ ★ 离线重算 ⇒ ★ **完全不必再调嵌入通道** ★★
★ ⇒ ★ ★ **★ 我方当前批的采集端【没有】落向量（★ 只落了 post 文本与 calls ★）★★**
★ ⇒ ★ ⇒ ★ **但 post 文本已落盘 ⇒ ⇒ 充值后重新向量化一次即可补上 ⇒ ⇒ 此后永久离线 ★★ ★
★ ⇒ ★ ★ **★ ⇒ 阻塞没有消失，★ 但它从【每批都要付】变成【只付一次】★★ ★
★ ⇒ ★ ⇒ ★ **且【越早做越好】**（★ 趁 post 文本还在、★ 单元清单还在 ★）
>
> ★ ★★ 五条硬纪律 ★★
★ ① **绝不降维**：★ 谱熵依赖【完整谱】⇒ ★ 先降维再存会让 Vendi 的值改变 ⇒ ★ 降维版【不能】替代原向量
★ ② **绝不试跑**：★ 嵌入通道不通 ⇒ **立即退出**（★ 与 `resume_after_window` 同一纪律 ★）⇒ ★ 不白烧额度
★ ③ **失败不静默**：★ 缺 post / 空 post / 维度不符 ⇒ **逐条记账**并写进 manifest ⇒ ★ 不静默变 0
★ ④ **补录件必须标 `provenance = post-hoc`**：★ 事后补录的向量与采集端向量【可能不是同一次调用产生的】
★    ⇒ ★ 不标 provenance ⇒ 外部无从判断【这批向量是哪来的】⇒ ★ **「同值 ≠ 同源」的最直接应用**
★ ⑤ **落盘位置不得在 `runs/`**：★ `runs/` 被 `.gitignore` 排除 ⇒ ★ 落在那里外部拿不到 ⇒ ★ 「可复核」是假的
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib as _hl
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

PROVENANCE = "post-hoc"          # ★ 纪律 ④ ★

# ★ ★ 与 client.LLM.embed 的【落盘缓存】共用的 key/path 算法（★ 单一真相源 ★）★★
#   ★ ⇒ ★ 补录件【同时】写成缓存格式 ⇒ ★ 之后任何脚本调 client.embed 都【零通道命中】★★
from creativity_lab.client import _cache_key, _cache_path, _utcnow  # noqa: E402
BATCH = 32                        # ★ 嵌入批量（★ 与 client.embed 的分块一致 ★）


def sha256_file(p: str) -> str:
    h = _hl.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def read_units(unit_list: str):
    out = []
    with open(unit_list, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(ln)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--unit-list", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--cache-dir", default="",
                    help="★ client.embed 的落盘缓存目录（★ 单一真相源：★ 与补录件同 key ★）")
    ap.add_argument("--dry-run", action="store_true", help="★ 只盘点不调通道（★ 零消耗 ★）")
    a = ap.parse_args()

    udir = os.path.join(a.run_dir, "units")
    if not os.path.isdir(udir):
        print("✘ 找不到单元目录：%s" % udir)
        return 2
    units = read_units(a.unit_list)
    ul_sha = sha256_file(a.unit_list)
    os.makedirs(a.out_dir, exist_ok=True)

    # ── ① 盘点（★ 不调通道 ★）──
    todo, have, failures = [], [], []
    for uid in units:
        vp = os.path.join(a.out_dir, "%s.json" % uid)
        if os.path.isfile(vp):
            have.append(uid)
            # ★ ★ 已有向量也【补写缓存格式】⇒ ★ 幂等补齐（★ 缓存与补录件同源 ★）★★
            try:
                _o = json.load(open(vp, encoding="utf-8"))
                _u = json.load(open(os.path.join(udir, "%s.json" % uid), encoding="utf-8"))
                _p = _u.get("post")
                _v = _o.get("vector")
                if isinstance(_p, str) and _p.strip() and _v:
                    _cp = _cache_path(a.cache_dir, _p, "db")
                    if not os.path.isfile(_cp):
                        os.makedirs(os.path.dirname(_cp), exist_ok=True)
                        _tmp = _cp + ".tmp"
                        with open(_tmp, "w", encoding="utf-8") as _f:
                            json.dump({"text_sha256": _cache_key(_p, "db"), "model": "embo-01",
                                       "type": "db", "dim": len(_v), "vector": _v,
                                       "cached_at_utc": _utcnow()}, _f, ensure_ascii=False)
                        os.replace(_tmp, _cp)
            except Exception:                                   # noqa: BLE001
                pass
            continue
        jp = os.path.join(udir, "%s.json" % uid)
        if not os.path.isfile(jp):
            failures.append({"unit": uid, "why": "unit json 不存在"})
            continue
        try:
            d = json.load(open(jp, encoding="utf-8"))
        except Exception as e:                                    # noqa: BLE001
            failures.append({"unit": uid, "why": "unit json 读不了：%s" % e})
            continue
        post = d.get("post")
        if not isinstance(post, str) or not post.strip():
            failures.append({"unit": uid, "why": "post 为空或缺失",
                             "post_source": d.get("post_source")})
            continue
        todo.append((uid, post))

    print("== ★ 事后补录 per-unit 原始向量（★ provenance = %s ★）==" % PROVENANCE)
    print("   单元清单：%s（%d 单元，★ sha256 %s…）" % (a.unit_list, len(units), ul_sha[:12]))
    print("   已有向量：%d ｜ 待补：%d ｜ 失败：%d" % (len(have), len(todo), len(failures)))
    print("   预计嵌入调用：%d 次（★ 批量 %d ★）" % ((len(todo) + BATCH - 1) // BATCH, BATCH))
    if failures:
        print("   ★ 失败清单（★ 逐条记账、★ 不静默 ★）：")
        for f in failures[:10]:
            print("     - %s：%s" % (f["unit"], f["why"]))
    if a.dry_run:
        print("   ⇒ ★ --dry-run：★ 零消耗、★ 未调通道 ★")
        return 0
    if not todo:
        print("   ⇒ 无需补录（★ 幂等 ★）")
        return 0

    # ── ② 嵌入通道实测（★ 纪律 ②：★ 不通就立刻退出、★ 绝不试跑 ★）──
    from creativity_lab.client import LLM
    llm = LLM()
    try:
        probe = llm.embed(["通道探针"], typ="db")
    except Exception as e:                                        # noqa: BLE001
        print("   ✘ 嵌入通道不通：%s" % e)
        print("   ⇒ ★ **绝不试跑** ⇒ 退出码 2（★ 未消耗任何额度 ★）")
        return 2
    if not probe or not isinstance(probe[0], list) or not probe[0]:
        print("   ✘ 嵌入通道返回异常（★ 疑似余额/额度问题 ★）⇒ 退出码 2")
        return 2
    dim = len(probe[0])
    print("   ✔ 嵌入通道通 ｜ 维度 = %d（★ 未降维 ★）" % dim)

    # ── ③ 逐批向量化并原子落盘 ──
    n_done = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        ids = [u for u, _ in chunk]
        texts = [t for _, t in chunk]
        try:
            vecs = llm.embed(texts, typ="db")
        except Exception as e:                                    # noqa: BLE001
            print("   ✘ 第 %d 批失败：%s" % (i, e))
            for uid in ids:
                failures.append({"unit": uid, "why": "嵌入失败：%s" % e})
            continue
        # ★★★★ 断长守卫：★ zip 会【静默截断】（★ 返回少于请求数 ⇒ 后面的 uid
        #   ★ 既不在 successes 也不在 failures ⇒ ⇒ exit 0、★ manifest 正常、★
        #   ★ 失败清单为空 ⇒ ⇒ 【一切自检全绿】而那批单元的向量【根本没落盘】★★ ★
        #   ★ ⇒ ★ 离线重算时它们会【被跳过或算错】⇒ ⇒ ★ 必须在 zip【之前】拦住 ★★★★
        if not isinstance(vecs, list) or len(vecs) != len(ids):
            _got = len(vecs) if isinstance(vecs, list) else "非list"
            print("   ✘✘ 第 %d 批返回条数不符：★ 请求 %d ⇒ 实得 %s ★ ⇒ ★ 【zip 会静默截断】★"
                  % (i, len(ids), _got))
            raise SystemExit(3)
        for uid, v in zip(ids, vecs):
            if not isinstance(v, list) or len(v) != dim:
                failures.append({"unit": uid, "why": "维度不符（%s ≠ %d）" % (len(v) if isinstance(v, list) else "?", dim)})
                continue
            obj = {"unit": uid, "provenance": PROVENANCE,
                   "backfilled_at_utc": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "batch_id": os.path.basename(a.run_dir.rstrip("/")),
                   "unit_list_sha256": ul_sha,
                   "model": "embo-01", "dim": dim, "normalized": False,
                   "vector": v}
            tmp = os.path.join(a.out_dir, "%s.json.tmp" % uid)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False)
            os.replace(tmp, os.path.join(a.out_dir, "%s.json" % uid))
            # ★ 同步写缓存格式（★ 单一真相源：★ 两者 key 相同 ★）★★
            _cp = _cache_path(a.cache_dir, dict((x[0], x[1]) for x in todo)[uid], "db")
            os.makedirs(os.path.dirname(_cp), exist_ok=True)
            _tmp2 = _cp + ".tmp"
            with open(_tmp2, "w", encoding="utf-8") as _f:
                json.dump({"text_sha256": _cache_key(dict((x[0], x[1]) for x in todo)[uid], "db"),
                           "model": "embo-01", "type": "db", "dim": len(v), "vector": v,
                           "cached_at_utc": _utcnow()}, _f, ensure_ascii=False)
            os.replace(_tmp2, _cp)
            n_done += 1
        print("   · 已补 %d / %d" % (n_done, len(todo)))

    # ── ④ manifest（★ 纪律 ④：★ 标 provenance + 覆盖范围 ★）──
    man = {"provenance": PROVENANCE,
           "backfilled_at_utc": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
           "batch_id": os.path.basename(a.run_dir.rstrip("/")),
           "run_dir": a.run_dir,
           "unit_list": a.unit_list, "unit_list_sha256": ul_sha,
           "n_units_in_list": len(units),
           "n_vectors_written": n_done,
           "dim": dim, "normalized": False,
           "note": "★ 事后补录件，★ 与采集端原生落盘件【不可混为一谈】★ ★ "
                   "★ 谱熵依赖完整谱 ⇒ ★ 本目录内【未做任何降维】★",
           "n_units_missing": 0,
           "failures": failures}
    # ★ 计数自检（★ 「各块之和 == N」的形态 ★）：★ 每个 uid 要么成功、要么进 failures
    #   ★ ⇒ ★ 二者之和必须等于 todo 的长度 ★ ⇒ ★ 否则有单元被【静默吞掉】★★ ★
    if n_done + len(failures) != len(todo):
        print("   ✘✘ 计数自检失败：★ 成功 %d + 失败 %d = %d ≠ 待补 %d ★ ⇒ ★ 【有单元被静默吞掉】★"
              % (n_done, len(failures), n_done + len(failures), len(todo)))
        raise SystemExit(3)
    mp = os.path.join(a.out_dir, "MANIFEST-%s.json" % PROVENANCE)
    tmp = mp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, mp)
    print("   ✔ manifest → %s" % mp)
    print("   ⇒ 补录 %d 个向量，★ 失败 %d 条（★ 逐条记账 ★）" % (n_done, len(failures)))
    print("   ⇒ ★ 此后 Vendi 与任何谱统计量【可离线重算】★ ⇒ ★ 不再需要第二次充值 ★")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
