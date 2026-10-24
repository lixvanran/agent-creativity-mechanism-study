#!/usr/bin/env python3
"""第四组 · v6 Stage-1 runner。

⚠️ 设计规格见 `STAGE1_SPEC.md`（事前写死）。⚠️ 预注册见 `PREREG_v6.md` v3。

执行顺序（**不可调换**）：
  1. 启动时落盘环境实际值（G0-1）
  2. 每题每 rep：① A 臂（直答，作 EscapeGate 的参照系）② 状态链（立场→初稿→观测→决策）
     ③ **K=3 候选（blind ⇒ 四格共享同一批候选）**
  ④ 三个选择结果：F=家族最优（不读状态，A≡C）/ B=状态化·无代价 / D=状态化·有代价
  ⑤ Stage-0 门活性检查（G0-4）—— **第一批候选后立刻做，不过就停**
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# ★★ G0-1：先钉环境变量，再 import 任何会读它的模块
ENV_SNAPSHOT = {
    "OPENROUTER_BASE_URL_before": os.environ.get("OPENROUTER_BASE_URL"),
    "OPENROUTER_BASE_URL_pinned": "https://api.minimaxi.com/v1",
    "MINIMAX_SUBSCRIPTION_KEY_set": bool(os.environ.get("MINIMAX_SUBSCRIPTION_KEY")),
    "G4_REF_DIR": os.environ.get("G4_REF_DIR", "/workspace/g4_ref"),
    "PYTHON": sys.version.split()[0],
    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
}
os.environ["OPENROUTER_BASE_URL"] = "https://api.minimaxi.com/v1"

import api_any                                            # noqa: E402
from api_any import chat, strip_think                     # noqa: E402
import workflow_arch5 as WA5                              # noqa: E402
import workflow_arch6 as W6                               # noqa: E402
from workflow_arch6 import FamilyScorers6, state_pick6, family_pick6, state_variants6, target_set6  # noqa: E402
from run_arch5_compare import build_state5                # noqa: E402  ← v5 复用（状态链）
from run_arch3_compare import step_stance3, step_observe3, step_decide  # noqa: E402

MODEL = "MiniMax-M3"
SAMPLE_WATCHDOG = 900      # ★ 单样本硬上限（秒）
K = 3
CAND_LO, CAND_HI = 600, 900

TOPICS = {
    "G01": "你如何看待高考英语作文？写成一篇文章。",
    "T07": None,     # 从 run_multitopic 的题库取（极简题面）
    "T10": None,
}


def load_topics() -> dict:
    """沿用 v3–v5 的同一批极简题面（G01/T07/T10）。"""
    out = {"G01": TOPICS["G01"]}
    try:
        from run_multitopic import MINIMAL
        for tid in ("T07", "T10"):
            q = MINIMAL.get(tid)
            if q:
                out[tid] = q
    except Exception as e:
        print("  ⚠️ 取 MINIMAL 题库失败：%s: %s" % (type(e).__name__, e))
    return out


# ─────────────────────────────────────────────────────────────
def run_A(question: str) -> dict:
    """A 臂：一次直答（**EscapeGate 的参照系**）。"""
    try:
        txt = strip_think(chat([{"role": "user", "content": question}],
                                model=MODEL, max_tokens=3200))
        return {"text": txt, "error": None}
    except Exception as e:
        return {"text": "", "error": "%s: %s" % (type(e).__name__, e)}


def gen_candidates_blind(st, k=K):
    """★ blind 候选（提示只给编号）⇒ **四格共享同一批候选**。"""
    out = []
    for i in range(1, k + 1):
        prompt = WA5.render_candidate_prompt5(st, CAND_LO, CAND_HI, blind=True,
                                               cand_no=i, k=k)
        try:
            raw = chat([{"role": "user", "content": prompt}], model=MODEL, max_tokens=3200)
            txt = strip_think(raw)
            w, d, rawline, ok = WA5.parse_declaration(txt)
            err = None if ok else "no_declaration"
            if ok and not (w or d):
                err = "empty_declaration"
            out.append(WA5.Candidate5(idx=i, text=txt, decl_write=w, decl_drop=d,
                                       decl_raw=rawline, decl_parsed=ok, error=err))
        except Exception as e:
            out.append(WA5.Candidate5(idx=i, text="",
                                      error="%s: %s" % (type(e).__name__, e)))
    return out


def embed_texts(texts, rec: list):
    """embedding（走 MiniMax 通道）⇒ 记进 recorder（**含失败**）。"""
    from creativity_lab.client import LLM
    llm = LLM(recorder=rec)
    try:
        return llm.embed(list(texts))
    except Exception as e:
        api_any.CALL_LOG.append({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "url": os.environ.get("OPENROUTER_BASE_URL", "") + "/embeddings",
            "model": "embo-01", "base_url": os.environ.get("OPENROUTER_BASE_URL"),
            "kind": "embedding", "prompt_chars": sum(len(t) for t in texts),
            "max_tokens": None, "attempts": 1,
            "errors": ["%s: %s" % (type(e).__name__, e)], "ok": False,
            "latency": None, "finish_reason": None, "usage": None,
        })
        raise


def one_sample(tag, topic_id, question, rep, batch_id):
    """跑一个 (题, rep) ⇒ 返回一条记录（含全部选择结果）。"""
    rec = {"arm": "V6-STAGE1", "tag": tag, "topic_id": topic_id, "rep": rep,
           "batch_id": batch_id, "model": MODEL, "question": question,
           "seed": None, "calls": [], "error": None}
    t0 = time.time()

    # ① A 臂（参照系）
    a = run_A(question)
    rec["A"] = {"text_len": len(a["text"]), "error": a["error"]}
    rec["calls"].append("A")

    # ② 状态链（复用 v5）
    try:
        st, smeta = build_state5(question)
    except Exception as e:
        rec["error"] = "state_build:%s: %s" % (type(e).__name__, e)
        rec["elapsed"] = round(time.time() - t0, 2)
        return rec
    rec["state_meta"] = smeta
    rec["calls"].extend(["stance", "draft", "observe", "decide"])

    if not st.gaps:
        rec["error"] = "no_gaps"
        rec["elapsed"] = round(time.time() - t0, 2)
        return rec

    # ③ 两个状态版本（gaps 相同 ⇒ 候选池共享）
    st_base, st_quota, qmeta = state_variants6(st)
    rec["quota_meta"] = qmeta
    tb, tq = target_set6(st_base), target_set6(st_quota)
    rec["target_base"] = tb
    rec["target_quota"] = tq
    # ★ 目标集变化率：**deep/drop 两项任一不同** ⇒ 代价真的进了状态
    rec["target_changed"] = bool(tb != tq)

    # ④ 候选（blind ⇒ 共享）
    cands = gen_candidates_blind(st_base)
    rec["calls"].extend(["cand%d" % c.idx for c in cands])
    rec["n_cand_ok"] = sum(1 for c in cands if not c.error and (c.text or "").strip())
    rec["n_cand_scored"] = rec["n_cand_ok"]
    rec["cand_errors"] = [c.error for c in cands if c.error]

    # ⑤ 参照系向量（A 臂产出）
    ref_vecs, embed_err = [], None
    try:
        if a["text"]:
            ref_vecs = embed_texts([a["text"]], rec.setdefault("_embed_rec", []))
    except Exception as e:
        embed_err = "%s: %s" % (type(e).__name__, e)
    rec["embed_error"] = embed_err
    rec["calls"].append("embed_ref")

    # ⑥ 三次选择
    # ★ EscapeGate 的 ref 实际当**文本**用（参数名 ref_vecs 有误导 ⇒ 见 workflow_arch6 注释）
    fam = FamilyScorers6(ref_texts=[a["text"]] if a["text"] else [])
    align = lambda c: WA5.score_state_alignment5(c, st_base)   # 家族比较用**同一基准**
    fp = family_pick6(cands, fam, align)
    rec["F_family"] = {"gate": fp.get("gate"), "align": fp.get("align"),
                       "picked_idx": fp.get("picked_idx"), "rank": fp.get("rank"),
                       "per_gate": fp.get("per_gate"), "diag": fp.get("diag")}
    sp_b = state_pick6(cands, st_base)
    sp_d = state_pick6(cands, st_quota)
    rec["B_state_nocost"] = {"picked_idx": sp_b.get("picked_idx"), "align": sp_b.get("align"),
                             "scores": sp_b.get("scores"), "rank": sp_b.get("rank")}
    rec["D_state_quota"] = {"picked_idx": sp_d.get("picked_idx"), "align": sp_d.get("align"),
                            "scores": sp_d.get("scores"), "rank": sp_d.get("rank")}
    # ★ 排序改变率（有代价：家族最优 F vs 状态化 D；无代价：F vs B）
    rec["sel_change_quota"] = W6.selection_change(fp.get("picked_idx"), sp_d.get("picked_idx"))
    rec["sel_change_nocost"] = W6.selection_change(fp.get("picked_idx"), sp_b.get("picked_idx"))
    # ★ 主读数：**完整排序**变化（top-1 对并列不敏感 ⇒ 会系统性低估）
    rec["rank_change_quota"] = W6.rank_change6(sp_b.get("rank"), sp_d.get("rank"))
    rec["rank_change_family"] = W6.rank_change6(fp.get("rank"), sp_d.get("rank"))

    # ⑦ 兑现 / 违禁（零判官）
    def _ful(cands_, idx, st_):
        if idx is None:
            return None
        c = next((x for x in cands_ if x.idx == idx), None)
        if c is None:
            return None
        return {"fulfill": WA5.score_fulfillment5(c, st_), "violation": WA5.score_violation5(c, st_)}
    rec["ful_B"] = _ful(cands, sp_b.get("picked_idx"), st_base)
    rec["ful_D"] = _ful(cands, sp_d.get("picked_idx"), st_quota)
    rec["ful_F"] = _ful(cands, fp.get("picked_idx"), st_base)

    rec["elapsed"] = round(time.time() - t0, 2)
    return rec


def _with_watchdog(fn, limit, *a, **kw):
    """在子线程里跑 fn；超过 limit 秒 ⇒ 主线程放弃并返回一条显式失败记录。"""
    import threading
    box = {}

    def _t():
        try:
            box["r"] = fn(*a, **kw)
        except Exception as e:
            box["e"] = "%s: %s" % (type(e).__name__, e)
    th = threading.Thread(target=_t, daemon=True)
    th.start()
    th.join(limit)
    if th.is_alive():
        return {"arm": "V6-STAGE1", "tag": a[0], "error": "watchdog_timeout:%ds" % limit,
                "watchdog": True}
    if "e" in box:
        raise RuntimeError(box["e"])
    return box.get("r")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", default="G01,T07,T10")
    ap.add_argument("--reps", default="1,2,3")
    ap.add_argument("--out", default=str(HERE / "runs" / "arch6_stage1.jsonl"))
    ap.add_argument("--batch-id", default=None)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    topics = load_topics()
    reps = [int(x) for x in args.reps.split(",") if x.strip()]
    tids = [t.strip() for t in args.topics.split(",") if t.strip()]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.append else "w"

    # ★ G0-1：环境实际值落盘
    envp = out.parent / "env_snapshot.json"
    envp.write_text(json.dumps(ENV_SNAPSHOT, ensure_ascii=False, indent=2), encoding="utf-8")
    print("── G0-1 环境快照 →", envp)
    for k, v in ENV_SNAPSHOT.items():
        print("   %-32s %s" % (k, v))
    print("   ★ 实际生效 OPENROUTER_BASE_URL =", os.environ.get("OPENROUTER_BASE_URL"))

    if args.dry_run:
        print("--dry-run：只打印题面与批号，不调用")
        for t in tids:
            print("   %s: %s" % (t, topics.get(t)))
        return

    with out.open(mode, encoding="utf-8") as f:
        for tid in tids:
            q = topics.get(tid)
            if not q:
                print("  ⚠️ 跳过未知题 %s" % tid)
                continue
            batch = args.batch_id or ("v6s1-%s-%s" % (tid, time.strftime("%Y%m%d-%H%M%S")))
            print("\n===== %s | batch=%s =====" % (tid, batch), flush=True)
            for rep in reps:
                tag = "%s-%s" % (tid, rep)
                try:
                    # ★ 单样本 watchdog：单样本超过 SAMPLE_WATCHDOG 秒 ⇒ 标记失败并继续
                    #   （实测教训：某次 HTTP 调用挂住 30 分钟未超时 ⇒ 整批卡死）
                    r = _with_watchdog(one_sample, SAMPLE_WATCHDOG, tag, tid, q, rep, batch)
                except Exception as e:
                    r = {"arm": "V6-STAGE1", "tag": tag, "topic_id": tid, "rep": rep,
                         "batch_id": batch, "error": "%s: %s" % (type(e).__name__, e)}
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
                print("   %-10s err=%s  cand_ok=%s  F=%s  B=%s  D=%s  Δq=%s" % (
                    tag, r.get("error"), r.get("n_cand_ok"),
                    (r.get("F_family") or {}).get("picked_idx"),
                    (r.get("B_state_nocost") or {}).get("picked_idx"),
                    (r.get("D_state_quota") or {}).get("picked_idx"),
                    r.get("sel_change_quota")), flush=True)

                # ★ G0-4 门活性检查：**第一批候选后立刻做**
                if rep == reps[0] and tid == tids[0]:
                    dg = (r.get("F_family") or {}).get("diag") or {}
                    print("   ── G0-4 门活性：%s" % json.dumps(dg, ensure_ascii=False))
                    # ★ G0-4 判据：**每个 Gate 都必须"活的"**
                    #   ① 不可用（ok=False / 无分数）⇒ 仪器层失败 ⇒ 停
                    #   ② 常量（var≈0）⇒ 静默退化成常量尺子 ⇒ 停
                    #   （length 允许常量吗？不允许——它若常量则家族只剩 1 把尺子）
                    # ★ spread 按**定义**就返回同一个值给所有候选 ⇒ 天然常量 ⇒ 不作判据
                    bad = []
                    for k in ("escape", "length"):
                        v = dg.get(k)
                        if v is None:
                            bad.append("%s:无诊断" % k); continue
                        if not v.get("ok"):
                            bad.append("%s:不可用(%s)" % (k, v.get("error")))
                        elif v.get("constant"):
                            bad.append("%s:常量(var=%s)" % (k, v.get("var")))
                    sp = dg.get("spread")
                    if sp is not None and not sp.get("ok"):
                        bad.append("spread:不可用(%s)" % sp.get("error"))
                    if bad:
                        print("   ✘✘ G0-4 不过：%s ⇒ 停止（仪器问题，非假设被否）" % bad)
                        break

    # ★ calllog 落盘（含失败调用）
    health = api_any.dump_calllog(out.parent / "calllog.jsonl")
    print("\n── 通道健康度（分母含失败调用）：%s" % json.dumps(health, ensure_ascii=False))
    print("── 输出：%s" % out)


if __name__ == "__main__":
    main()
