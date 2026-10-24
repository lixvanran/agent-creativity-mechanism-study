"""臂3 / 臂4 · 双轴架构。**两者的唯一差异是末步。**

轴A VARIANCE  → 每个分支一个独立调用，零共享上下文（治链内锚定）
轴B PARTITION → 跨模型档位 + 不同 persona（治知识不分区）

末步两种：
  fuse   —— 把分支材料综合成一篇答复（融合门）
  select —— 各分支已各自成篇，末步只挑一篇，原样输出

规格、认知框架、persona 全部放在 prompts.py，与代码分离，
这样 leakage.py 能只扫「真正发给模型的字符串」。
"""
from creativity_lab.arms.base import ArmResult
from creativity_lab.client import MODELS
from creativity_lab.prompts import (FRAMES, PERSONAS, OUT_SPEC, PREMISE_Q,
                                    BRANCH_ASK, FUSE_ASK, SELECT_ASK)

N_BRANCH = 5

# ★ ★ ★ min_ok 定版表（★ 2026-10-24 · 全部【回源真实 prompt 的输出规格】★★ ★
# ★   ★ 依据：★ client.chat 的 min_ok 是【内容长度下限】★ 默认 200 ⇒ ★
# ★   ★   ★ 【统一 200 会把【一批正常输出】判成失败】⇒ ★ 阈值必须与规格【一起定版】★★ ★
# ★   ★ 依据表：★
# ★   ★   步骤        prompt        输出规格                          min_ok
# ★   ★   diverge     BRANCH_ASK   OUT_SPEC「400 字以内」             120
# ★   ★   premise     PREMISE_Q    【150–250 字】                     120
# ★   ★   fuse        FUSE_ASK     OUT_SPEC「400 字以内」             120
# ★   ★   select      SELECT_ASK   理由 60–120 字 + 原样贴被选篇全文   20（★ 结构判据兜底 ★）
# ★   ★ ★ ⇒ 统一 120 也不行：★ 120 落在 diverge/fuse 的正常分布（200–500）内 ⇒ ★ 短返回污染
# ★   ★ ★ ⇒ 所以【按臂分别定版】+【select 另用结构判据】⇒ ★ 两件事都要做 ★★★ ★
MIN_OK_DIVERGE = 120
MIN_OK_PREMISE = 120
MIN_OK_FUSE = 120
MIN_OK_SELECT = 20


def _branch_specs(alive=None):
    """轴A × 轴B 的联合扇出：框架/模型/persona 三者错位绑定。

    ★ `alive`（2026-10-24）：★ **可注入的型号池** ★
    ⇒ 用途：★ **剔掉已下架型号**（★ M2.1 / M2 实测 404 ⇒ 5 支静默变 4 支 ★）★
    ⇒ ★ 形态照抄 `creativity_lab/experiments/cogpos_matrix.py:104` 的
      `build_specs(arm, alive)`（★ 本仓的现成先例 ★）★ ★ 不另发明 ★★
    ⇒ ★ 只换【型号】★，★ 框架/persona 的错位绑定结构**完全不动** ★
      ⇒ ★ 符合"单一因子改动" ★
    ★ ★ `alive` 为 None ⇒ 行为与旧版逐位相同（向后兼容）★★
    """
    models = list(alive) if alive else MODELS
    return [(FRAMES[i % len(FRAMES)], models[i % len(models)], PERSONAS[i % len(PERSONAS)])
            for i in range(N_BRANCH)]


class Dual:
    """mode='fuse' → 臂3；mode='select' → 臂4。发散层完全相同。"""

    def __init__(self, mode: str, select: str = "greedy"):
        assert mode in ("fuse", "select")
        self.name = f"dual_{mode}"
        self.mode, self.select = mode, select

    # ---------- 发散层 ----------
    def _diverge(self, llm, topic, *, produce_article: bool, specs=None):
        """★ `specs` 可注入（2026-10-23）：分支的模型档位可以指定，
        用于**剔掉已下架型号**（M2.1 实测 404 ⇒ 5 支静默变 4 支），
        且把"用哪些模型"记进 manifest（可审计）。

        ★★ 2026-10-24：★ **失败必须【显式记账】，不能靠"过滤掉空串"★**
        ⇒ ★ 旧实现 `return [o for o in outs if o]` ⇒ ★ 下架型号返空 ⇒ ★ **静默少一支** ★
        ⇒ ★ 现在：★ 循环内判空 ⇒ ★ 记进 `failed` ⇒ ★ 由 `run()` 落进 `ArmResult.notes` ★
        ⇒ ★ **语义等价**（输出集合不变）★，★ **但证据不丢** ★★
        """
        specs = specs or _branch_specs()
        outs = []
        failed = []
        for (frame, model, persona) in specs:
            prompt = (BRANCH_ASK.format(
                topic=topic["ask"], frame_name=frame["name"], frame_text=frame["text"],
                persona=persona, spec=OUT_SPEC,
                extra="\n直接写出**完整的答复本身**，不要写判断片段。" if produce_article
                     else "\n写出这个位置上会看到的**判断与依据**，不要写成文。"))
            # ★ ★ min_ok 按【本步骤的输出规格】定版（★ 2026-10-24 · 第 1 层论证线那条 ★）★★
            #   ★ BRANCH_ASK ⇒ OUT_SPEC「控制在 400 字以内」⇒ ★ 正常分布 200–500
            #   ★ ⇒ ★ 不传则吃 client.chat 的默认 200 ⇒ ★ 【误杀正常短输出】★★ ★
            out = llm.chat(prompt, model=model, purpose=f"diverge:{model}",
                           min_ok=MIN_OK_DIVERGE)
            if out and out.strip():
                outs.append(out)
            else:
                failed.append(model)
        self.last_failed = failed
        return outs

    # ---------- 臂3：融合门 ----------
    def _fuse(self, llm, topic, frags):
        pre = llm.chat(PREMISE_Q.format(n=len(frags), cands="\n\n".join(
            f"[{i+1}] {c[:400]}" for i, c in enumerate(frags))), purpose="premise",
            # ★ PREMISE_Q 的规格是【150–250 字】⇒ ★ 默认 200 ⇒ ★ 【150–200 的正常输出被误杀】★★ ★
            min_ok=MIN_OK_PREMISE)
        return llm.chat(FUSE_ASK.format(topic=topic["ask"],
                                        frags="\n\n".join(f"[{i+1}] {c[:400]}" for i, c in enumerate(frags)),
                                        pre=pre[:700], spec=OUT_SPEC), purpose="fuse",
                                        # ★ FUSE_ASK ⇒ OUT_SPEC「400 字以内」★
                                        min_ok=MIN_OK_FUSE)

    # ---------- 臂4：只选不融 ----------
    def _select(self, llm, topic, arts):
        out = self._select_raw(llm, topic, arts)
        # ★ ★ 结构判据（★ 2026-10-24 · 第 1 层论证线 12:55Z 那条 · ★ 他们实测抓到 4 例 ★）★★ ★
        #   ★ `SELECT_ASK` 的规格是「★ 先写 60–120 字理由、★ 再【原样贴出被选篇全文】★」
        #   ★ ⇒ ★ 【原样贴出】是【结构要求】⇒ ★ 光看长度【挡不住】★ ⇒ ★ 必须核【子串包含】★★ ★
        #   ★ ★ ⇒ ★ 实现：★ 找出【是输出子串的分支】里最长的那篇 ⇒ ★ 其长度 > 0 ⇒ 结构符合 ★★★ ★
        #   ★ ★ ⇒ ★ 关键：★ `sel_len == 0` ⇒ 【一律无效】（★ 哪怕输出很长 ★）★★ ★
        best = 0
        for a in (arts or []):
            if a and a in out:
                best = max(best, len(a))
        self.last_sel_len = best
        self.last_sel_n_arts = len(arts or [])
        return out

    def _select_raw(self, llm, topic, arts):
        return llm.chat(SELECT_ASK.format(
            n=len(arts),
            arts="\n\n=====\n\n".join(f"[第{i+1}篇]\n{a}" for i, a in enumerate(arts)),
            spec=OUT_SPEC), purpose="select",
            # ★ ★ SELECT_ASK 的输出 = 【理由 60–120 字】+【原样贴出被选篇全文】★
            #   ★ ⇒ ★ 被选篇本身短时【总长可以 < 200】⇒ ★ 默认 200 ⇒ ★ 【会把一批正常输出判成失败】★★ ★
            #   ★ ⇒ ★ ⇒ ★ 20 只挡空串/截断；★ ★ 有效性另用【结构判据】（★ 见 run() ★）★★ ★
            min_ok=MIN_OK_SELECT)

    def run(self, llm, topic, rep, specs=None):
        """★ `specs`（2026-10-24）★ **对外暴露**型号池注入 ★
        ⇒ ★ 用途：剔掉已下架型号（★ M2.1 / M2 实测 404 ⇒ 5 支静默变 4 支 ★）
        ⇒ ★ **默认路径行为完全不变**（★ `specs=None` ⇒ 旧版逐位相同 ★）★★
        ★ ★ `notes` 落三个数（★ 臂级失败记账 ★）★★
        · `n_specs`       = 计划支数
        · `models_used`   = 真正拿到正文的型号（★ 去重后有序 ★）
        · `models_failed` = 返空的型号（★ **失败路径不许静默归零** ★）
        ⇒ ★ 「计划 5 / 实际 4」这个差额在 notes 里**一眼可见** ★
        """
        _struct_bad = False
        if self.mode == "fuse":
            frags = self._diverge(llm, topic, produce_article=False, specs=specs)
            text = self._fuse(llm, topic, frags) if frags else ""
        else:
            arts = self._diverge(llm, topic, produce_article=True, specs=specs)
            text = self._select(llm, topic, arts) if arts else ""
            # ★ ★ 结构判据：★ `sel_len == 0` ⇒ 【一律无效】★★ ★
            #   ★ ★ ⇒ ★ 【不采信「输出非空」】★ ⇒ ★ 型号可能被改写了被选篇（★ 违反 SELECT_ASK 规格 ★）★★ ★
            #   ★ ★ ⇒ ★ 无效 ⇒ ★ 置空 text（★ 语义：没有有效产出 ★）+ notes 登记（★ 失败不许静默 ★）★★ ★
            _sel_len = int(getattr(self, "last_sel_len", 0) or 0)
            _struct_bad = bool(text) and _sel_len == 0
        used, failed = [], list(getattr(self, "last_failed", []) or [])
        for (_f, m, _p) in (specs or _branch_specs()):
            if m not in failed and m not in used:
                used.append(m)
        notes = {"n_specs": len(specs or _branch_specs()),
                 "models_used": used,
                 "models_failed": failed}
        if self.mode != "fuse":
            notes["sel_len"] = int(getattr(self, "last_sel_len", 0) or 0)
            notes["n_arts"] = int(getattr(self, "last_sel_n_arts", 0) or 0)
            if _struct_bad:
                notes["structure_mismatch_no_selected_branch"] = True
                notes["invalid_reason"] = "structure_mismatch_no_selected_branch"
                text = ""          # ★ ★ 置空 ⇒ 无效（★ 不进任何读数的分子/分母 ★）★★ ★
        return ArmResult(self.name, topic["tid"], rep, text,
                         len(frags if self.mode == "fuse" else arts) if text else 0,
                         notes=notes)
