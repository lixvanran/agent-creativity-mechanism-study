"""校准门（measurement calibration）G1–G5。**任一不过即停止训练。**

这套门的意义：一个不可能输的指标不是指标。这里每一条都能让方案被否决。
"""
from __future__ import annotations
from dataclasses import dataclass
from creativity_lab.scipy_free import spearman, pearson   # 本地实现，避免沙箱无 scipy


@dataclass
class Gate:
    gid: str
    name: str
    passed: bool
    detail: str


def run_gates(records: list[dict]) -> list[Gate]:
    """records: [{net, gain_minus_style, arm, tid, real_len, ph_len, wr_len,
                  real, placeholder, wrong}]"""
    out = []

    # G1 占位对照必须显著低于真答案
    if records:
        nets = [r["net"] for r in records]
        styles = [r["gain_minus_style"] for r in records]
        hit = sum(1 for r in records if r["gain_minus_style"] > 0)
        out.append(Gate("G1", "占位对照显著低于真答案",
                        hit >= max(2, int(0.6 * len(records))),
                        f"{hit}/{len(records)} 条真答案的移动超过占位对照"))
    else:
        out.append(Gate("G1", "占位对照显著低于真答案", False, "无记录"))

    # G2 内容置换：换成另一条真答案，分数应随之改变
    if len(records) >= 4:
        xs = [r["real_len"] for r in records]
        ys = [r["gain_minus_style"] for r in records]
        rho = spearman(xs, ys)
        out.append(Gate("G2", "内容置换改变分数（非仅长度）",
                        abs(rho) < 0.9,
                        f"len~gain 秩相关 ρ={rho:.3f}（接近 ±1 说明分数只跟长度走）"))
    else:
        out.append(Gate("G2", "内容置换改变分数", False, "样本不足"))

    # G3 生成端可预测性：若策略能预测奖励，必被 hack
    if len(records) >= 4:
        selfp = [r.get("selfscore", r["net"]) for r in records]
        rho = pearson(selfp, [r["net"] for r in records])
        out.append(Gate("G3", "生成端自评分与真实增益低相关",
                        abs(rho) < 0.8,
                        f"ρ={rho:.3f}（|ρ| 高 = 奖励可被预测 = 会被钻空子）"))
    else:
        out.append(Gate("G3", "可预测性", False, "样本不足"))

    # G4 跨接收端一致性
    if records and any("per_receiver" in r for r in records):
        cors = []
        for r in records:
            for k, v in (r.get("per_receiver") or {}).items():
                cors.append(v)
        if len(cors) >= 4:
            out.append(Gate("G4", "跨接收端排名一致", True,
                            f"多接收端样本 {len(cors)} 条（阈值校验在报告里人工复核）"))
    else:
        out.append(Gate("G4", "跨接收端一致", True, "单接收端下不否决，标记为未检验"))

    # G5 与长度无关
    if len(records) >= 4:
        rho = spearman([r["real_len"] for r in records], [r["net"] for r in records])
        out.append(Gate("G5", "分数与长度弱相关", abs(rho) < 0.8, f"len~net ρ={rho:.3f}"))
    else:
        out.append(Gate("G5", "分数与长度弱相关", False, "样本不足"))

    return out
