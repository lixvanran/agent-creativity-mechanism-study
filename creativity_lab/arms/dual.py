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


def _branch_specs(alive=None):
    """轴A × 轴B 的联合扇出：框架/模型/persona 三者错位绑定。

    ★ `alive`（2026-10-26）：★ **可注入的型号池** ★
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

        ★★ 2026-10-26：★ **失败必须【显式记账】，不能靠"过滤掉空串"★**
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
            out = llm.chat(prompt, model=model, purpose=f"diverge:{model}")
            if out and out.strip():
                outs.append(out)
            else:
                failed.append(model)
        self.last_failed = failed
        return outs

    # ---------- 臂3：融合门 ----------
    def _fuse(self, llm, topic, frags):
        pre = llm.chat(PREMISE_Q.format(n=len(frags), cands="\n\n".join(
            f"[{i+1}] {c[:400]}" for i, c in enumerate(frags))), purpose="premise")
        return llm.chat(FUSE_ASK.format(topic=topic["ask"],
                                        frags="\n\n".join(f"[{i+1}] {c[:400]}" for i, c in enumerate(frags)),
                                        pre=pre[:700], spec=OUT_SPEC), purpose="fuse")

    # ---------- 臂4：只选不融 ----------
    def _select(self, llm, topic, arts):
        return llm.chat(SELECT_ASK.format(
            n=len(arts),
            arts="\n\n=====\n\n".join(f"[第{i+1}篇]\n{a}" for i, a in enumerate(arts)),
            spec=OUT_SPEC), purpose="select")

    def run(self, llm, topic, rep, specs=None):
        """★ `specs`（2026-10-26）★ **对外暴露**型号池注入 ★
        ⇒ ★ 用途：剔掉已下架型号（★ M2.1 / M2 实测 404 ⇒ 5 支静默变 4 支 ★）
        ⇒ ★ **默认路径行为完全不变**（★ `specs=None` ⇒ 旧版逐位相同 ★）★★
        ★ ★ `notes` 落三个数（★ 臂级失败记账 ★）★★
        · `n_specs`       = 计划支数
        · `models_used`   = 真正拿到正文的型号（★ 去重后有序 ★）
        · `models_failed` = 返空的型号（★ **失败路径不许静默归零** ★）
        ⇒ ★ 「计划 5 / 实际 4」这个差额在 notes 里**一眼可见** ★
        """
        if self.mode == "fuse":
            frags = self._diverge(llm, topic, produce_article=False, specs=specs)
            text = self._fuse(llm, topic, frags) if frags else ""
        else:
            arts = self._diverge(llm, topic, produce_article=True, specs=specs)
            text = self._select(llm, topic, arts) if arts else ""
        used, failed = [], list(getattr(self, "last_failed", []) or [])
        for (_f, m, _p) in (specs or _branch_specs()):
            if m not in failed and m not in used:
                used.append(m)
        notes = {"n_specs": len(specs or _branch_specs()),
                 "models_used": used,
                 "models_failed": failed}
        return ArmResult(self.name, topic["tid"], rep, text,
                         len(frags if self.mode == "fuse" else arts) if text else 0,
                         notes=notes)
