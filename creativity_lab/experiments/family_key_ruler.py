#!/usr/bin/env python3
"""★ **第五把尺子：结论族去重（语义级）—— 零 API 归族**

> 落点：`creativity_lab/experiments/family_key_ruler.py`
> 输入：`docs/cmp8/batch-U1/measurement_v2.json`（★ **`cards_all` 的 schema 齐备**：
> `claim` / `verdict` / `evidence_ref` / `evidence_class` / `load_bearing` / `decision_changed` / **`supports_conclusions`**）
> 输出：`runs/family-key-2026-10-24/family_key.json`
>
> ## ★★★ 为什么这条是"零 API"
> ★ 三组给的 `family_key` 函数本体只是 3 行字符串操作，★ **归并的语义在判官那一半** ⇒
> ⇒ 复现这套口径 = 复现判官那一半 ⇒ ★★ **而这批的判官【已经跑过了】⇒ ⇒ `supports_conclusions` 已在盘上**
> ⇒ ⇒ **⇒ 归族这一步是纯离线重算 ⇒ 0 次 API 调用**
>
> ## ★★ 三个口径（★ 一次算齐，分开报）
> | 量 | 含义 |
> |---|---|
> | `n_families_loadbearing` | 承重卡里**已编号**的族数（★ 主读数）|
> | `n_families_all` | 全部卡去重（★ **含空族 `''`** ⇒ ★ 它是「未覆盖族 + 无价值卡」的混合体 ⇒ **引用必须写明**）|
> | `n_uncovered` | ★ **承重 ∧ 挂不上编号** ⇒ **单列，不并入任何族** |
> | `coverage` | `1 − n_uncovered / n_load_bearing` ⇒ ★ **结论空间覆盖率**（分母完整性）|
> | `n_uncovered_rate` | ★ **覆盖外主张率**（★ 单列单名 ⇒ 可能是创造性的代理）|
>
> ## ★★ 与前四把尺子的分工
> Vendi / modes / structured_dedup / self-BLEU 都是**表面或结构层**的量
> ⇒ ⇒ **本尺子是唯一能看见「它们说的是不是同一件事」的一把**
> ⇒ ⇒ ★ **正面命中 Vendi 的盲点**：★ 2 同向 + 2 反向 ⇒ Vendi = 1.00（判成同一模态）⇒ ⇒ 本尺子会分成两族
"""
import json
import os
import sys
from collections import Counter
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from creativity_lab.experiments import guard_io  # noqa: E402

from creativity_lab.metrics_ext import (family_key, family_three_calibers,   # noqa: E402
                                         family_uncovered_count)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "docs", "cmp8", "batch-U1", "measurement_v2.json")
OUT = os.path.join(ROOT, "runs", "family-key-2026-10-24", "family_key.json")


def _norm(c: Dict[str, Any]) -> Dict[str, Any]:
    """★ 把 `supports_conclusions` 归一成字符串列表（盘上是整数 `[10]`）。"""
    sc = c.get("supports_conclusions") or []
    if isinstance(sc, str):
        sc = [sc]
    return dict(c, supports_conclusions=[str(x) for x in sc])


def _collect_cards(d: Any, path: str = "") -> List[Dict[str, Any]]:
    """★ 自动探测所有「含 supports_conclusions 的卡列表」⇒ 任何卡池都能直接跑。"""
    out: List[Dict[str, Any]] = []
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "supports_conclusions" in v[0]:
                out.append((path + k, v))
            out += _collect_cards(v, path + k + ".")
    elif isinstance(d, list):
        for i, v in enumerate(d[:50]):
            out += _collect_cards(v, path + "[%d]." % i)
    return out


def main() -> int:
    d = json.load(open(SRC, encoding="utf-8"))
    res = d.get("results") or {}
    rows: List[Dict[str, Any]] = []
    for key, r in res.items():
        cards_all = [_norm(c) for c in (r.get("cards_all") or [])]
        cards_kept = [_norm(c) for c in (r.get("cards_kept") or [])]
        if not cards_all:
            continue
        cal_all = family_three_calibers(cards_all)
        cal_kept = family_three_calibers(cards_kept) if cards_kept else None
        # ★ 空族的异质性（★ 三组实测的关键分布：空族里 21% 是「承重却挂不上编号」）
        empty = [c for c in cards_all if not c.get("supports_conclusions")]
        empty_dist = Counter((bool(c.get("load_bearing")), c.get("verdict")) for c in empty)
        rows.append(dict(
            arm_key=key, arm=r.get("arm"), rep=r.get("rep"),
            n_cards=len(cards_all), n_kept=len(cards_kept),
            n_load_bearing=r.get("n_load_bearing_cards"),
            n_dimensions=r.get("n_dimensions"),
            conclusions_supported=r.get("conclusions_supported"),
            # ── 三口径 ──
            fam_all=cal_all["n_families_loadbearing"],
            fam_allcards=cal_all["n_families_all"],
            n_uncovered=cal_all["n_uncovered"],
            n_load_bearing_cal=cal_all["n_load_bearing"],
            coverage=round(cal_all["coverage"], 4) if cal_all["n_load_bearing"] else None,
            # ── 未覆盖族：分母完整性 vs 覆盖外主张（★ 分开命名）──
            n_uncovered_rate=round(cal_all["n_uncovered"] / cal_all["n_load_bearing"], 4)
            if cal_all["n_load_bearing"] else None,
            empty_family_cards=len(empty),
            empty_family_dist={("LB" if k[0] else "nonLB") + "/" + str(k[1]): v
                               for k, v in empty_dist.items()},
            # ── 已编号族的分布（★ 族的大小）──
            family_sizes=sorted(Counter(
                family_key(c) for c in cards_all if c.get("supports_conclusions")
            ).values(), reverse=True),
        ))

    print("== ★ 第五把尺子：结论族去重（语义级）｜零 API 归族 ==")
    print("%-24s %-7s %-6s %-7s %-7s %-9s %-9s %-8s" %
          ("臂#rep", "n卡", "承重", "承重族", "全卡族", "未覆盖", "覆盖率", "覆盖外率"))
    for r in rows:
        print("%-24s %-7s %-6s %-7s %-7s %-9s %-9s %-8s" %
              (r["arm_key"], r["n_cards"], r["n_load_bearing_cal"], r["fam_all"],
               r["fam_allcards"], r["n_uncovered"],
               ("%.3f" % r["coverage"]) if r["coverage"] is not None else "-",
               ("%.3f" % r["n_uncovered_rate"]) if r["n_uncovered_rate"] is not None else "-"))
    print()
    # ★ 空族异质性汇总（★ 三组 367 张卡上的分布 ⇒ 本批是否同型）
    agg = Counter()
    for r in rows:
        for k, v in (r["empty_family_dist"] or {}).items():
            agg[k] += v
    tot_empty = sum(agg.values())
    tot_uncovered = sum(r["n_uncovered"] for r in rows)
    print("★ 空族异质性（本批合计 %d 张空族卡）：" % tot_empty)
    for k, v in sorted(agg.items(), key=lambda x: -x[1]):
        print("   %-22s %4d  (%.1f%%)" % (k, v, v / tot_empty * 100 if tot_empty else 0))
    print("   ⇒ ★★ 承重却挂不上编号 = %d 张（%.1f%%）⇒ ★ %s"
          % (tot_uncovered, tot_uncovered / tot_empty * 100 if tot_empty else 0,
             "★ 与三组实测（21%）同型 ⇒ 第五把尺子确实照出了「表面同一模态、实际两族」"
             if tot_empty and tot_uncovered / tot_empty > 0.1 else "★ 与三组实测不同型 ⇒ 需说明"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"rows": rows, "n_calls_api": 0,
               "source": "docs/cmp8/batch-U1/measurement_v2.json",
               "calibers": ["n_families_loadbearing", "n_families_all", "n_uncovered",
                            "coverage", "n_uncovered_rate"],
               "empty_family_aggregate": dict(agg),
               "n_uncovered_total": tot_uncovered},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    # ★ 扫所有卡池
    print()
    print("== ★ 全仓卡池扫描（第五把尺子的可覆盖面）==")
    pools = scan_all_pools()
    tot = Counter()
    for p in pools:
        tot["n_cards"] += p["n_cards"]
        tot["n_uncovered"] += p["n_uncovered"]
        tot["n_load_bearing"] += p["n_load_bearing"]
    for p in sorted(pools, key=lambda x: -x["n_cards"])[:18]:
        print("   %-58s %-30s 卡=%-3d 承重=%-3d 承重族=%-3d 未覆盖=%-3d 覆盖率=%s"
              % (p["pool"][-58:], p["key"][-30:], p["n_cards"], p["n_load_bearing"],
                 p["fam_loadbearing"], p["n_uncovered"],
                 ("%.3f" % p["coverage"]) if p["coverage"] is not None else "-"))
    print("   ⇒ 合计：卡 %d ｜ 承重 %d ｜ 未覆盖 %d（%.1f%% of 承重）"
          % (tot["n_cards"], tot["n_load_bearing"], tot["n_uncovered"],
             tot["n_uncovered"] / tot["n_load_bearing"] * 100 if tot["n_load_bearing"] else 0))
    # ★★ 底本版本 + 命题条数（★ 负责人 2026-10-24 要求：换底本会改未覆盖率 ⇒ 不标就会有人把旧底本的数当现状）
    d0 = json.load(open(SRC, encoding="utf-8"))
    baseline = {"measure_version": d0.get("measure_version"),
                "n_propositions": d0.get("facts"),
                "evidence_hash": str(d0.get("evidence_hash"))[:32],
                "judge_model": d0.get("judge_model"),
                "★ caveat": ("★ 本读数的结论空间挂的是【U1-measure-v1-2026-10-21 底本】；"
                             "★ 三组 2026-10-24 已把底本换成 v2（69 条命题）⇒ ⇒ "
                             "★ ⇒ 本表的『未覆盖率』里有相当一部分可能是【底本旧 ⇒ 挂不上编号】，"
                             "而不是『模型说出了结论空间之外的东西』⇒ ⇒ ★ 该数【暂不可对外报】⇒ "
                             "★ 等 v2 底本落地后用 v2 + 69 条命题重算 ⇒ 那次重算会给出"
                             "『换底本值多少』的真数")}

    json.dump({"rows": rows, "pools": pools,
               "pool_totals": dict(tot), "n_calls_api": 0,
               "baseline": baseline,
               "source": "docs/cmp8/batch-U1/measurement_v2.json + 全仓卡池扫描"},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print("\n== ★ 底本标注 ==")
    print("   measure_version : %s" % baseline["measure_version"])
    print("   n_propositions  : %s" % baseline["n_propositions"])
    print("   evidence_hash   : %s" % baseline["evidence_hash"])
    print("   ★ caveat        : %s" % baseline["★ caveat"][:120])
    print("\n✔ 落盘：%s" % OUT)
    return 0


def scan_all_pools():
    """★ 扫仓内所有卡池 ⇒ 第五把尺子的读数不止一个来源。"""
    import glob
    pools = []
    # ★★★ 输入/输出隔离（★ 2026-10-24 统一形态：★ 解析输入的同一处就断言，★ realpath 级）
    guard_io.assert_output_outside_input_dir(ROOT, os.path.dirname(OUT), "family_key_ruler")
    for pat in ("docs/cmp8/routes/COLLAPSE/eval/runs/dev/anchor_calibration*/calibration.json",
                "docs/cmp8/routes/COLLAPSE/eval/runs/dev/judge_variants/judge_variants.json",
                "docs/cmp8/batch-U1/measurement*.json"):
        for p in sorted(glob.glob(os.path.join(ROOT, pat))):
            try:
                d = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            for path, cards in _collect_cards(d):
                if not cards:
                    continue
                nc = [_norm(c) for c in cards]
                cal = family_three_calibers(nc)
                empty = [c for c in nc if not c.get("supports_conclusions")]
                unc = family_uncovered_count(nc)
                pools.append(dict(pool=os.path.relpath(p, ROOT), key=path, n_cards=len(nc),
                                  n_load_bearing=cal["n_load_bearing"],
                                  fam_loadbearing=cal["n_families_loadbearing"],
                                  fam_all=cal["n_families_all"], n_uncovered=unc,
                                  coverage=round(cal["coverage"], 4) if cal["n_load_bearing"] else None,
                                  n_uncovered_rate=round(unc / cal["n_load_bearing"], 4)
                                  if cal["n_load_bearing"] else None,
                                  empty_family=len(empty)))
    return pools


if __name__ == "__main__":
    raise SystemExit(main())
