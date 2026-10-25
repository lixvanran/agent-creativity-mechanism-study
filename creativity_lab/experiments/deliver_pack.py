#!/usr/bin/env python3
"""★ **交付打包器（★ 通道 B / C 的可执行形态）**

> 落点：`creativity_lab/experiments/deliver_pack.py`
> 用法：
> ```bash
> python3 -B creativity_lab/experiments/deliver_pack.py --run <run_dir> [--out <zip>]
> python3 -B creativity_lab/experiments/deliver_pack.py --self-test
> ```
>
> ## ★★ 为什么要有这个（★ 2026-10-25 PAT 失效后，★ 通道 B/C 是【主通道】不是兜底）
> ★ 通道 A（GitHub）因 Classic PAT 吊销而不可用 ⇒ ⇒ **交付责任全在 B/C**
> ⇒ ⇒ ★ **⇒ 交付必须【一条命令、零手工、零外部依赖】⇒ ⇒ 且必须【自带可核验性】**
>
> ## ★★ 三件它做的事
> ① **打包**（★ zip）★★ ② **MANIFEST 清单式校验**（★ 查漏 / 查多 / 查改）★★ ③ **生成【纯文本读数包】**（★ 通道 C）
>
> ## ★★★ ★ 校验的期望值从哪来（★ 这是最关键的一点）
> ★ **期望值来自【打包时生成的 MANIFEST.json】（★ 路径 + sha256 + size）⇒ ⇒ 不是来自被检查对象自己**
> ⇒ ⇒ ★ **★ 如果期望值来自 zip 自己（★ 比如"数文件数 == 数文件数"）⇒ ⇒ 恒真 ⇒ ⇒ 检查项直接报废**
> ⇒ ⇒ ★ **★ 而且【MANIFEST 自身不入清单】⇒ ⇒ 否则它自己的哈希会自我指涉**
> ⇒ ⇒ ★ **★ 第三类「内容被改」是【数个数】永远抓不到的 ⇒ ⇒ 只有 sha256 能抓**
>
> ## ★★★ 负向自测（★ 证明检查项是活的）
> ★ `--self-test`：★ 故意改一个文件 / 加一个文件 / 删一个文件 ⇒ ⇒ **校验必须逐条报错**
> ⇒ ⇒ ★ **★ 否则你不知道它是活的（★ 「我加了自检」这件事本身要验伪）**
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile

# ★★★ 路径必须【realpath 归一】：★ 同一个目录有两个别名（★ /workspace/lab 是符号链接，
# ★ 真实路径是 NFS 挂载点 /run/csi/mount-root/nas/<id>/lab）⇒ ⇒ ★ 用字符串 startswith
# ★ 判断"是否在仓内"会【失效】⇒ ⇒ ★ relpath 会算出绝对路径 ⇒ ⇒ ★ os.path.join 遇绝对路径
# ★ 会【丢弃前缀】⇒ ⇒ ★ dst == src ⇒ ⇒ SameFileError。
# ★ ★ 通则：★ 凡做路径包含/相对化，★ 两端都先 realpath；★ 判据用 os.path.commonpath
# ★ 而不是字符串 startswith（★ 因为 /a/bc 以 /a/b 开头但并不在它下面）。
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.realpath(_ROOT)
REPORT = "/workspace/第二组交付报告_2026-10-25.md"

# ★ 随包必带的文件（★ 相对仓库根）
ALWAYS = [
    "creativity_lab/state_layer.py",
    "creativity_lab/experiments/test_state_layer.py",
    "creativity_lab/experiments/check_readout_liveness.py",
    "creativity_lab/experiments/verify_anchors.py",
    "creativity_lab/experiments/h0_calibration.py",
    "creativity_lab/experiments/endstep_newlost_probe.py",
    "creativity_lab/metrics_ext.py",
    "docs/cmp8/routes/COLLAPSE/eval/PREREG-TOPOLOGY-ARM.md",
    "docs/cmp8/routes/COLLAPSE/eval/MAS_Diversity-ACTUAL-CONFIGS.md",
    "docs/交接/WORKPACK-1-evidence-entry.md",
    "docs/交接/WORKPACK-2-stem-chain.md",
    "docs/交接/WORKPACK-2-state-chain.md",
    "docs/交接/WORKPACK-2-humanities-chain.md",
    "docs/交接/WORKPACK-3-min-architecture.md",
    "docs/交接/WORKPACK-3-equilength-design.md",
    "docs/交接/STATE-LAYER-ASSESSMENT.md",
]


def _rel(p: str) -> str:
    """★ 把绝对路径变成【仓内相对路径】（★ ★ 两端都 realpath ⇒ ★ 别名问题消失）。"""
    pr = os.path.realpath(p)
    try:
        r = os.path.relpath(pr, ROOT)
    except ValueError:
        r = os.path.basename(pr)
    if r.startswith("..") or os.path.isabs(r):
        # ★ 不在仓内 ⇒ 放进 EXTRA/ 并压平路径（★ ★ 绝不能让它变成绝对路径）
        r = os.path.join("EXTRA", pr.replace(os.sep, "_").lstrip("_"))
    return r


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def collect(run_dir: str, stage: str) -> dict:
    """★ 收集待打包文件（★ 相对路径 → 绝对路径）。"""
    files = {}
    for rel in ALWAYS:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            files[rel] = os.path.realpath(p)
    if os.path.exists(run_dir):
        rdir_real = os.path.realpath(run_dir)
        for dp, dns, fns in os.walk(rdir_real):
            dns[:] = [d for d in dns if d != "__pycache__"]
            for fn in fns:
                if fn.endswith(".pyc"):
                    continue
                p = os.path.join(dp, fn)
                rel = _rel(p)
                files[rel] = p
    if os.path.exists(REPORT):
        files[os.path.basename(REPORT)] = REPORT
    return files


def write_manifest(files: dict, mpath: str) -> dict:
    """★ ★ MANIFEST 生成（★ 自身不入清单 ⇒ ★ 避免自我指涉）。"""
    man = {"version": 1,
           "note": ("★ 期望值的唯一来源 ⇒ ★ 查漏/查多/查改都以此为准"
                    "｜★ MANIFEST 自身不入清单"),
           "files": []}
    for rel in sorted(files):
        p = files[rel]
        man["files"].append({"path": rel, "size": os.path.getsize(p),
                             "sha256": sha256_of(p)})
    man["n_files"] = len(man["files"])
    man["total_bytes"] = sum(f["size"] for f in man["files"])
    tmp = mpath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, mpath)          # ★ 原子写
    return man


def verify(pack_dir: str) -> list:
    """★ ★ 三查：查漏 / 查多 / 查改（★ 期望值 = MANIFEST）。"""
    mpath = os.path.join(pack_dir, "MANIFEST.json")
    if not os.path.exists(mpath):
        return ["✘ MANIFEST 缺失 ⇒ 无法校验"]
    man = json.load(open(mpath, encoding="utf-8"))
    want = {f["path"]: f for f in man["files"]}
    errs = []
    # ── 实际存在的文件（排除 MANIFEST 自身）──
    actual = {}
    for dp, dns, fns in os.walk(pack_dir):
        dns[:] = [d for d in dns if d != "__pycache__"]
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, pack_dir)
            if rel == "MANIFEST.json":
                continue
            actual[rel] = p
    # ① 查漏
    for rel in want:
        if rel not in actual:
            errs.append("✘ 查漏：MANIFEST 里有、包里没有 ⇒ %s" % rel)
    # ② 查多
    for rel in actual:
        if rel not in want:
            errs.append("✘ 查多：包里有、MANIFEST 里没有 ⇒ %s" % rel)
    # ③ 查改
    for rel, meta in want.items():
        if rel not in actual:
            continue
        got = sha256_of(actual[rel])
        if got != meta["sha256"]:
            errs.append("✘ 查改：内容被改 ⇒ %s（期望 %s / 实得 %s）"
                        % (rel, meta["sha256"][:16], got[:16]))
    return errs


def read_text_report(run_dir: str) -> str:
    """★ ★ 通道 C 的内容：★ 纯文本读数包（★ 不依赖任何文件通道）。"""
    lines = []
    lines.append("=" * 72)
    lines.append("【第二组 · 拓扑臂读数包（★ 通道 C · 纯文本 · 零文件依赖）】")
    lines.append("生成时间：%s" % __import__("datetime").datetime.now().isoformat(timespec="seconds"))
    lines.append("run_dir：%s" % run_dir)
    lines.append("=" * 72)
    mpath = os.path.join(run_dir, "manifest.json")
    if not os.path.exists(mpath):
        lines.append("★ manifest 尚未生成（★ 批未收尾）")
        return "\n".join(lines)
    m = json.load(open(mpath, encoding="utf-8"))
    lines.append("")
    lines.append("── ① 口径声明（★ 判决前必读）──")
    for k in ("n_unit_definition", "main_readout_layer", "aux_readout_layer",
              "two_readout_layers", "ngt_semantics_source", "leader_definition",
              "per_arm_calls", "comparability", "factorial_decomposition",
              "quota_note"):
        if k in m:
            lines.append("  · %s：%s" % (k, m[k]))
    lines.append("")
    lines.append("── ② 健康度与额度（★ 通道健康度 ⇒ 分母含失败调用）──")
    lines.append("  · health：%s" % json.dumps(m.get("health"), ensure_ascii=False))
    lines.append("  · finish_reason_dist：%s" % json.dumps(m.get("finish_reason_dist"), ensure_ascii=False))
    lines.append("  · n_failed_calls：%s" % m.get("n_failed_calls"))
    lines.append("  · health_checkpoints：%s" % json.dumps(m.get("health_checkpoints"), ensure_ascii=False)[:1200])
    if m.get("stopped_early"):
        lines.append("  ★ 早停：%s" % json.dumps(m["stopped_early"], ensure_ascii=False))
    lines.append("")
    lines.append("── ③ 逐臂读数表（★ n 单元数 / 主层 / 辅层 / 三把尺子）──")
    for g in m.get("groups") or []:
        lines.append("  【%s r%s】" % (g.get("tid"), g.get("rep")))
        for arm, a in (g.get("arms") or {}).items():
            rp = a.get("read_post") or {}
            rq = a.get("read_pre") or {}
            lines.append("    · %-16s n_units=%s n_post=%s n_pre=%s calls=%s failed=%s"
                         % (arm, a.get("n_units"), a.get("n_post"), a.get("n_pre"),
                            a.get("n_calls"), a.get("n_failed")))
            lines.append("        主层：%s" % json.dumps(rp, ensure_ascii=False))
            lines.append("        辅层：%s" % json.dumps(rq, ensure_ascii=False))
    lines.append("")
    lines.append("── ④ H0 标定（★ 两批合并 21 个同题配对差 · Wilson 95% 区间）──")
    hp = os.path.join(run_dir, "h0_calibration.json")
    if os.path.exists(hp):
        h = json.load(open(hp, encoding="utf-8"))
        lines.append("  · n_total=%s ｜ rate=%.4f ｜ ci95=%s ｜ 与 50%% 相差 %+.4f"
                     % (h.get("n_total"), h.get("rate", 0), h.get("ci95"),
                        h.get("delta_from_50", 0)))
    else:
        lines.append("  ★ 尚未生成（★ 跑 h0_calibration.py 后重发本包）")
    lines.append("")
    lines.append("── ⑤ 活性检查（★ 事后质量门：只能否证、不能正证）──")
    lp = os.path.join(run_dir, "liveness_check.json")
    if os.path.exists(lp):
        l = json.load(open(lp, encoding="utf-8"))
        lines.append("  · ok=%s ｜ issues=%d ｜ notes=%d" % (l.get("ok"),
                     len(l.get("issues") or []), len(l.get("notes") or [])))
        for x in (l.get("issues") or [])[:20]:
            lines.append("    ★ %s" % x)
        for x in (l.get("notes") or [])[:10]:
            lines.append("    · %s" % x)
    else:
        lines.append("  ★ 尚未生成（★ 跑 check_readout_liveness.py 后重发本包）")
    lines.append("")
    lines.append("── ⑥ 判决（★ ★ 只能填数、★ 不得改判据）──")
    lines.append("  ★ 判据版本 = 正式批启动时的 HEAD = 17244d2d329c69939e88476f3a93d275ec7296a6")
    lines.append("  ★ 判决表：H-TOPO-4a（交互效应）/ 4c（综述效应）/ 4d（可见性图效应）")
    lines.append("  ★ 四种状态：成立 / 未观察到支持 / 不可分辨 / 未检验")
    lines.append("  ★ ★ 禁止写法：「topo 比 nosel 分散 X%」（★ 那个差值混着两个因子）")
    lines.append("=" * 72)
    return "\n".join(lines)


def build(run_dir: str, out_zip: str, stage: str) -> int:
    files = collect(run_dir, stage)
    tmp = tempfile.mkdtemp(prefix="deliverpack_")
    try:
        for rel, p in files.items():
            dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(p, dst)
        mpath = os.path.join(tmp, "MANIFEST.json")
        man = write_manifest(files, mpath)
        # ★ 打包（★ MANIFEST 在最前 ⇒ ⇒ 外部先看清单再核内容）
        if os.path.exists(out_zip):
            os.remove(out_zip)
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(mpath, "MANIFEST.json")
            for rel in sorted(files):
                z.write(os.path.join(tmp, rel), rel)
        errs = verify(tmp)
        print("== ★ 交付打包（★ 通道 B）==")
        print("   zip：%s（%d B）" % (out_zip, os.path.getsize(out_zip)))
        print("   MANIFEST：%d 个文件 / %d B" % (man["n_files"], man["total_bytes"]))
        if errs:
            print("   ✘ 校验失败 %d 项：" % len(errs))
            for e in errs[:20]:
                print("     ", e)
            return 1
        print("   ✔ 校验通过（★ 查漏 / 查多 / 查改 三查全过）")
        print()
        print(read_text_report(run_dir))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def self_test() -> int:
    """★ ★ 负向自测：★ 故意破坏 ⇒ ⇒ 校验必须逐条报错（★ 否则检查项是死的）。"""
    print("== ★ 交付打包器 · 负向自测（★ 证明检查项是活的）==")
    tmp = tempfile.mkdtemp(prefix="dptest_")
    try:
        f1 = os.path.join(tmp, "a.txt")
        f2 = os.path.join(tmp, "b.txt")
        open(f1, "w").write("hello")
        open(f2, "w").write("world")
        files = {"a.txt": f1, "b.txt": f2}
        write_manifest(files, os.path.join(tmp, "MANIFEST.json"))
        errs = verify(tmp)
        print("  %s 完好包 ⇒ 无错（★ 期望）" % ("✔" if not errs else "✘"))
        if errs:
            for e in errs:
                print("     ", e)
            return 1
        # ① 查改：改内容但条目数不变
        open(f1, "w").write("HELLO")
        errs = verify(tmp)
        hit = any("查改" in e for e in errs)
        print("  %s 变异①：改内容（★ 条目数不变）⇒ 报" % ("✔" if hit else "✘"))
        if not hit:
            print("     ★ 没报 ⇒ 检查项是死的")
            return 1
        for e in errs:
            print("     ", e)
        open(f1, "w").write("hello")
        # ② 查多：加一个 MANIFEST 里没有的文件
        open(os.path.join(tmp, "c.txt"), "w").write("extra")
        errs = verify(tmp)
        hit = any("查多" in e for e in errs)
        print("  %s 变异②：加文件 ⇒ 报" % ("✔" if hit else "✘"))
        if not hit:
            return 1
        for e in errs:
            print("     ", e)
        os.remove(os.path.join(tmp, "c.txt"))
        # ③ 查漏：删一个 MANIFEST 里有的文件
        os.remove(os.path.join(tmp, "b.txt"))
        errs = verify(tmp)
        hit = any("查漏" in e for e in errs)
        print("  %s 变异③：删文件 ⇒ 报" % ("✔" if hit else "✘"))
        if not hit:
            return 1
        for e in errs:
            print("     ", e)
        print()
        print("✔ 负向自测通过（★ 三个变异都被抓住 ⇒ ★ 检查项是活的）")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="", help="★ run 目录（★ 如 runs/topo-arm-v2-2026-10-25）")
    ap.add_argument("--out", default="/workspace/第二组交付_2026-10-26.zip")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.run:
        ap.print_help()
        return 2
    return build(a.run, a.out, "final")


if __name__ == "__main__":
    raise SystemExit(main())
