"""臂1 · 直接调用。任何架构的参照系。

注意：输出规格与其他臂一致（由 prompts.OUT_SPEC 提供），
否则字数会成为混淆源 —— v3 实验里臂3 的中位字数只有 254，融合门在压字数。
"""
from creativity_lab.arms.base import ArmResult
from creativity_lab.prompts import OUT_SPEC


class Direct:
    name = "direct"

    def run(self, llm, topic, rep):
        t = llm.chat(topic["ask"] + "\n\n" + OUT_SPEC, purpose="direct")
        return ArmResult(self.name, topic["tid"], rep, t, 0)
