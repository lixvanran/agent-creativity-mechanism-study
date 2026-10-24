#!/usr/bin/env python3
"""★ **接口修订应用脚本（★ 自验证 · ★ 接收方只需运行它）**

> 落点：`creativity_lab/experiments/apply_state_layer_rev1.py`
> 目标：★ 把 `state_layer.py` 从旧版（`38795bf6adfdee05`）升级到新版（`69a29c506a4e4ab0`）
>
> ## ★★★ ★ 为什么是【脚本】而不是【diff 文本】（★ 这条是今天最重要的一条教训）
> ★ **2026-10-24 19:5x**：★ 我在给第四组的直发消息里贴了一份 `git diff`，
> ★ **而我【手抄】了其中一段 ⇒ ⇒ 抄错了（★ 多出一个 `if False else`）**
> ★ ⇒ ⇒ ★ **⇒ 于是我在同一条消息里【先发了坏的、再发了好的】⇒ ⇒ 这比"分两条发"更糟**
> ★ ⇒ ⇒ ★★★★ **⇒ 而我上一句刚宣称"★ diff 从结构上不可能美化 ★"⇒ ⇒ ★ 我当场被自己打了脸**
> ⇒ ⇒ ★★★ **⇒ 真解法不是"用 diff 代替全文"（★ 那只是换了个抄的对象）**
> ⇒ ⇒ ★★★ **⇒ 真解法是：★ 【让输出可被证伪】⇒ ⇒ ★ 接收方运行脚本 ⇒ ⇒ 脚本自己打印 sha256**
> ⇒ ⇒ ★★★★ **⇒ 若 sha256 不等于预期 ⇒ ⇒ 脚本【自己报错退出】⇒ ⇒ ★ 此时【我手写的文本】这个漏洞就被【输出校验】堵住了**
> ⇒ ⇒ ★★★ **⇒ 由此得到一条通则（★ 跨项目）：★ 「不要在传输层重新生产内容」是【弱纪律】（靠我不手抖）；
> ★ ★ 「让接收方从【原始来源】自己取 + 让输出【可被 sha256 证伪】」才是【强纪律】（★ 靠机制）】**
>
> ## ★ 用法
> ```bash
> python3 apply_state_layer_rev1.py <state_layer.py 路径>
> # ⇒ 打印新 sha256；若不等于 69a29c506a4e4ab0 ⇒ 退出码非零
> ```
"""
import hashlib
import os
import sys

EXPECT_SHA = "69a29c506a4e4ab0"
OLD_SHA = "38795bf6adfdee05"

# ★ ★ 四处修订（★ 每处都是【文本替换】⇒ ★ 替换后由 sha256 裁决对错 ⇒ ★ 不靠肉眼）
PATCHES = [
    # ① 两个阈值常量
    ('''HYP_SUPPORTED = "supported"
''',
     '''HYP_SUPPORTED = "supported"

# ★ ★ 两个阈值（★ 第四组 2026-10-24 独立审计后新增 ⇒ ★ 都是【人写死的固定规则】）
# ★ 死路判定看【连续】无新信息的次数（★ 不是累计）★★
DEAD_END_THRESHOLD = 3
# ★ 假设转 `supported` 所需的【支持性证据】条数（★ 一次不算 ⇒ 两次才算）★★
SUPPORT_THRESHOLD = 2
'''),
    # ② Attempt 加连续计数字段
    ('''@dataclass
class Attempt:
    """★ 已尝试方法（★ 记录尝试了什么、产生了什么新信息）"""
    method: str
    used: int = 0
    produced_new: bool = False
    dead_end: bool = False''',
     '''@dataclass
class Attempt:
    """★ 已尝试方法（★ 记录尝试了什么、产生了什么新信息）

    ★★ `consecutive_no_new` 与 `used` 的区别（★ 第四组 2026-10-24 独立审计发现 ⇒ ★ 真 bug）：
    ★ **`used` 是【累计】尝试次数；★ `consecutive_no_new` 是【连续无新信息】的次数**
    ★ ⇒ ⇒ ★ **判死路必须看【连续】而不是【累计】** ⇒ ⇒ ★
    ★ ★ **否则 `(True, True, False)` 这种"成功过两次、最近一次没进展"的方法会被误判成死路**
    """
    method: str
    used: int = 0
    produced_new: bool = False
    consecutive_no_new: int = 0     # ★ ★ 连续无新信息的次数（★ 判死路只看这个）
    dead_end: bool = False'''),
    # ③ 死路判定：累计 → 连续
    ('''    at.used += 1
    at.produced_new = produced_new
    # ★ 死路判定：★ 连续 3 次尝试都没有新信息 ⇒ 标记死路
    if not produced_new and at.used >= 3:
        at.dead_end = True
        s.progress.append("dead_end:%s" % method)
    return s''',
     '''    at.used += 1
    at.produced_new = produced_new
    # ★ ★ 死路判定：★ 【连续】3 次无新信息（★ 不是累计 3 次）
    if produced_new:
        at.consecutive_no_new = 0          # ★ ★ 有新信息 ⇒ 连续计数【清零】
    else:
        at.consecutive_no_new += 1
    if at.consecutive_no_new >= DEAD_END_THRESHOLD:
        at.dead_end = True
        s.progress.append("dead_end:%s" % method)
    return s'''),
    # ④ add_evidence：支持性证据 → supported + 留痕
    ('''def add_evidence(st: State, hid: str, ev: Dict[str, Any], refutes: bool = False) -> State:
    """★ **检验**：★ 追加证据；★ 若该证据【反证】假设 ⇒ 假设被推翻"""
    s = st.clone()
    for h in s.hypotheses:
        if h.hid == hid:
            h.add_evidence(ev)
            if refutes:
                h.status = HYP_REFUTED
                s.progress.append("refuted:%s" % hid)
            return s
    return s''',
     '''def add_evidence(st: State, hid: str, ev: Dict[str, Any], refutes: bool = False) -> State:
    """★ **检验**：★ 追加证据；★ 若该证据【反证】假设 ⇒ 假设被推翻；
    ★ 若该证据【支持】假设 ⇒ 累积到阈值 ⇒ 假设转 `supported`（★ 第四组 2026-10-24 独立审计发现 ⇒ ★ 真 bug）

    ★★ **为什么必须有 `supported` 这条路径（★ 原实现的后果）**：
    ★ 原实现里 `add_evidence(refutes=False)` 【不改变 status】⇒ ⇒ 假设永远停在 `open`
    ⇒ ⇒ ★ 而 `choose_action` 里 `check_hypothesis` 分支【优先于】`connect`
    ⇒ ⇒ ★ ⇒ **分歧连接被无限期阻塞**（★ 第四组实测：10 次支持性证据 + 1 条合法分歧 ⇒ 仍返回 `check_hypothesis`）
    ⇒ ⇒ ★★ **⇒ 修法：★ 支持性证据累积到 `SUPPORT_THRESHOLD` 条 ⇒ ⇒ 假设转 `supported` ⇒ ⇒ 不再阻塞 `connect`**

    ★★ **`SUPPORT_THRESHOLD = 2` 的理由**：★ **一次支持不算"被支持"**（★ 一次可能是噪声）★ ★
    ★ **两次独立支持才算** ⇒ ⇒ ★ ★ **但这是一个【新自由度】⇒ ⇒ 第四组接线时可在 manifest 里显式覆盖**
    """
    s = st.clone()
    for h in s.hypotheses:
        if h.hid == hid:
            h.add_evidence(ev)
            if refutes:
                h.status = HYP_REFUTED
                s.progress.append("refuted:%s" % hid)
            else:
                # ★ ★ 支持性证据也要留痕（★ 状态回放要能区分支持与反证）
                n_sup = sum(1 for e in h.evidence if not e.get("refutes"))
                s.progress.append("evidence:%s:support:%d" % (hid, n_sup))
                if n_sup >= SUPPORT_THRESHOLD and h.status == HYP_OPEN:
                    h.status = HYP_SUPPORTED
                    s.progress.append("supported:%s" % hid)
            return s
    return s'''),
    # ⑤ 新增 detect_tie（★ 接口层提供能力，★ 接线由第四组做）
    ('''def preserve_divergence(st: State, d: Dict[str, Any]) -> State:''',
     '''def detect_tie(scores: List[float], tol: float = 1e-9) -> Dict[str, Any]:
    """★ **并列检测**（★ 第四组 2026-10-24 提出 ⇒ ★ 裁决：★ 接口层提供能力，★ 接线由第四组做）

    ★ **为什么放在接口层**：★ 「两个候选评分并列 ⇒ 它们是合法分歧」是【规则的一部分】，
    ★ ★ **不该靠调用方记得去调 `preserve_divergence`** ⇒ ⇒ ★ 否则接线时一漏，分歧语义就丢了
    ★ ★（★ 第四组已报告：★ 他们的 `Select(greedy)` 【会吃掉并列】⇒ ⇒ ★ 这正是必须补的一步）

    ★ **返回**：★ 有并列 ⇒ 返回 `{"kind": "tie", "members": [...], "scores": [...]}`；
    ★ 无并列 ⇒ 返回 `None`
    ★ ★ **本函数【不修改状态】** ⇒ ⇒ ★ 接线方式由调用方决定（★ 通常是：
    ★ `if detect_tie(...) is not None: st = preserve_divergence(st, detect_tie(...))`）
    """
    if not scores:
        return None
    best = max(scores)
    members = [i for i, v in enumerate(scores) if abs(v - best) <= tol]
    if len(members) < 2:
        return None
    return {"kind": "tie", "members": members,
            "scores": [scores[i] for i in members]}


def preserve_divergence(st: State, d: Dict[str, Any]) -> State:'''),
]


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python3 apply_state_layer_rev1.py <state_layer.py>")
        return 2
    p = sys.argv[1]
    if not os.path.exists(p):
        print("✘ 文件不存在：%s" % p)
        return 2
    before = sha256_of(p)
    print("== ★ 接口修订 rev1（★ 自验证）==")
    print("   修订前 sha256：%s" % before[:16])
    if before.startswith(EXPECT_SHA):
        print("   ★ 已经是新版（%s）⇒ 无需修改" % EXPECT_SHA)
        print("   ✔ sha256 = %s ✔" % EXPECT_SHA)
        return 0
    if before.startswith(OLD_SHA):
        print("   ✔ 识别为旧版（%s）" % OLD_SHA)
    else:
        # ★ ★ 兜底路径：★ 不是精确旧版 ⇒ ⇒ 【不盲改】⇒ ⇒ 改用【锚点唯一命中】判定
        # ★ ★（★ 第四组那份可能因自建微调而与我们的旧版略有差异 ⇒ ★ 仍应能应用）
        print("   ★ sha256 与旧版不同（%s）⇒ ★ 改走【锚点唯一命中】路径" % before[:16])
        print("   ★ ★ 仍不盲改：★ 5 个锚点必须各命中【恰好 1 次】才动手")
    s = open(p, encoding="utf-8").read()
    for i, (a, b) in enumerate(PATCHES, 1):
        cnt = s.count(a)
        if cnt != 1:
            print("   ✘ 补丁 %d 锚点命中 %d 次（★ 期望恰好 1 次）⇒ 停止" % (i, cnt))
            return 2
        s = s.replace(a, b)
        print("   ✔ 补丁 %d/%d 已应用" % (i, len(PATCHES)))
    # ★ 原子写
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(s)
    os.replace(tmp, p)
    after = sha256_of(p)
    print("   修订后 sha256：%s" % after[:16])
    if not after.startswith(EXPECT_SHA):
        print("   ✘✘✘ sha256 不等于预期 %s ⇒ ★ 【应用失败】⇒ ★ 不要自行「修」⇒ ★ 请把文件 diff 回来" % EXPECT_SHA)
        return 1
    print()
    print("✔ 应用成功且【自验证通过】：sha256 = %s" % EXPECT_SHA)
    print("★ ★ 现在可以跑：python3 -B creativity_lab/experiments/test_state_layer.py（★ 期望 6 组全过）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
