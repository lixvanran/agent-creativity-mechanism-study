# -*- coding: utf-8 -*-
"""生成判读页：7 臂 × 4 题 × 3 重复的原始答案 + 机器指标。

用户是最终裁判（模型自测不能替代人工基准），所以这一页的设计目标是
**让人能逐条看完并下判断**，而不是替用户下结论。
"""
from __future__ import annotations

import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("CMP_OUT", "runs/cmp8")
ARMS = ["A1", "A2", "A3", "A4", "A5a", "A5b", "A5c"]
ARM_NAME = {
    "A1": "① 直调", "A2": "② 开源ADHD项目(机制复现)", "A3": "③ 双轴·融合门",
    "A4": "④ 双轴·去融合门", "A5a": "⑤a 新架构·无核验(控制)",
    "A5b": "⑤b 新架构·学到的策略", "A5c": "⑤c 新架构·初始w=0(控制)",
}
ARM_ROLE = {
    "A1": "基线", "A2": "外部项目（机制复现，非原版本体）", "A3": "旧架构",
    "A4": "旧架构（最强）", "A5a": "控制：隔离「有没有 oracle」",
    "A5b": "主实验", "A5c": "控制：隔离「学到的权重有没有用」",
}
TIDS = ["A1", "A2", "A3", "A4"]
QNAME = {"A1": "湖北620分选AI专业", "A2": "公路赛个人赛战术",
         "A3": "假期最后一天作业没动", "A4": "解读气质量表得分"}


def read(p):
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def main():
    an = json.load(open("%s/analysis.json" % OUT, encoding="utf-8"))
    summ = {s["arm"]: s for s in an["summary"]}
    H = []
    H.append("""<!doctype html><meta charset="utf-8">
<title>五族对比实验 · 用户的四道题</title>
<style>
:root{--bg:#0f1115;--fg:#e6e6e6;--dim:#9aa4b2;--line:#252a33;--acc:#7cc4fa;--warn:#ffb86b;--ok:#7ee787;--card:#161a21}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.75 -apple-system,"PingFang SC","Noto Sans CJK SC",Segoe UI,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:32px 22px 80px}
h1{font-size:25px;margin:0 0 6px}h2{font-size:19px;margin:40px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
h3{font-size:16px;margin:26px 0 10px;color:var(--acc)}
.sub{color:var(--dim);font-size:13.5px;margin-bottom:8px}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:13.5px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:right;vertical-align:top}
th{background:#1b2029;color:var(--dim);font-weight:600;text-align:right}
td:first-child,th:first-child{text-align:left}
tr:hover td{background:#1a1f27}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}
.ans{white-space:pre-wrap;font-size:14px;line-height:1.8}
details{border:1px solid var(--line);border-radius:9px;margin:9px 0;background:#12161d}
summary{cursor:pointer;padding:10px 14px;font-size:14px;color:var(--acc);user-select:none}
summary:hover{background:#181d25}
details .inner{padding:4px 16px 14px}
.tag{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:20px;border:1px solid var(--line);color:var(--dim);margin-left:8px}
.tag.main{color:#0f1115;background:var(--ok);border-color:var(--ok)}
.tag.ctrl{color:#0f1115;background:var(--warn);border-color:var(--warn)}
.box{border-left:3px solid var(--acc);background:#141922;padding:12px 16px;margin:14px 0;border-radius:0 8px 8px 0}
.box.warn{border-left-color:var(--warn)}
.kv{font-size:13.5px;color:var(--dim)} .kv b{color:var(--fg)}
pre{background:#0b0e13;border:1px solid var(--line);padding:10px;border-radius:8px;overflow:auto;font-size:12.5px}
</style><div class="wrap">""")
    H.append("<h1>五族对比实验 · 用户的四道题</h1>")
    H.append('<div class="sub">7 臂 × 4 题 × 3 重复 ｜ 每臂用同一模型集、同一判官、同一批依据包 ｜ '
             '判官 = %s（跨厂商）｜ embedding = OpenRouter</div>'
             % an.get("judge", "OpenRouter"))
    H.append('<div class="box warn"><b>臂2 是机制复现</b>（照搬 ADHD 项目的 engine.ts/frames.ts/render.ts，'
             '只换传输层；原版走 claude-agent-sdk 的通道当天挂死）。'
             '<b>最终评分仍由人做</b>：下面的指标只是辅助。</div>')

    H.append("<h2>一、机器指标</h2>")
    H.append('<div class="sub">width=去重后断言数（模型会在一份答案里把同一事实说 3–4 遍，'
             '任何按断言条数算的量都必须先去重）；union=3 份去重并集宽度；'
             '矛盾率=矛盾/(支持+矛盾)——唯一有方差、能当仲裁器的量；离散度=3 份两两语义距离均值</div>')
    H.append("<table><tr><th>臂</th><th>角色</th><th>字符</th><th>去重宽</th><th>并集宽</th>"
             "<th>矛盾率</th><th>支持率</th><th>离散度</th><th>未提及</th></tr>")
    for a in ARMS:
        s = summ.get(a)
        if not s:
            continue
        pt = s["per_t"]

        def m(k):
            vals = [v[k] for v in pt.values()]
            return sum(vals) / max(len(vals), 1)
        disp = [v["disp"] for v in pt.values() if v.get("disp") is not None]
        tag = ('<span class="tag main">主实验</span>' if a == "A5b"
               else ('<span class="tag ctrl">控制</span>' if a in ("A5a", "A5c") else ""))
        H.append("<tr><td>%s%s</td><td style='text-align:left;color:#9aa4b2'>%s</td>"
                 "<td>%.0f</td><td>%.1f</td><td>%.1f</td><td>%.1f%%</td><td>%.1f%%</td>"
                 "<td>%.3f</td><td>%.1f</td></tr>"
                 % (ARM_NAME[a], tag, ARM_ROLE[a], m("chars"), m("width"), m("union_width"),
                    100 * m("conflict"), 100 * m("support"),
                    sum(disp) / max(len(disp), 1) if disp else 0, m("unt")))
    H.append("</table>")

    H.append("<h2>二、逐题</h2>")
    for t in TIDS:
        H.append("<h3>%s（题号 %s）</h3>" % (QNAME[t], t))
        H.append("<table><tr><th>臂</th><th>字符</th><th>去重宽</th><th>并集宽</th>"
                 "<th>矛盾</th><th>支持</th><th>未提及</th><th>非主张</th></tr>")
        for a in ARMS:
            s = summ.get(a, {}).get("per_t", {}).get(t)
            if not s:
                continue
            H.append("<tr><td style='text-align:left'>%s</td><td>%.0f</td><td>%.1f</td><td>%d</td>"
                     "<td>%d</td><td>%d</td><td>%.1f</td><td>%.1f</td></tr>"
                     % (ARM_NAME[a], s["chars"], s["width"], s["union_width"],
                        s["conflict"] * s.get("n_legal", 0), s["support"] * s.get("n_legal", 0),
                        s["unt"], s["nc"]))
        H.append("</table>")

    H.append("<h2>三、原始答案（人工判读）</h2>")
    H.append('<div class="sub">每一格都是模型真实输出。⑤a/b/c 展示的是<b>合成版</b>'
             '（与其它臂同为流式答复）；机械装配版另附在每格末尾。</div>')
    for t in TIDS:
        H.append("<h3>%s</h3>" % QNAME[t])
        for a in ARMS:
            H.append("<details><summary>%s</summary><div class='inner'>" % ARM_NAME[a])
            any_txt = False
            for rep in (1, 2, 3):
                p = "%s/%s_r%d_%s_synth.md" % (OUT, t, rep, a)
                txt = read(p)
                if not txt.strip():
                    txt = read("%s/%s_r%d_%s.md" % (OUT, t, rep, a))
                if not txt.strip():
                    continue
                any_txt = True
                H.append("<div class='card'><div class='kv' style='margin-bottom:6px'>"
                         "<b>重复 %d</b> · %d 字符</div><div class='ans'>%s</div></div>"
                         % (rep, len(txt), html.escape(txt)))
            if not any_txt:
                H.append("<div class='card'><div class='ans' style='color:#ff6b6b'>"
                         "（该臂在此题无输出）</div></div>")
            if a.startswith("A5"):
                mech = read("%s/%s_r%d_%s.md" % (OUT, t, 1, a))
                if mech:
                    H.append("<details><summary>机械装配版（架构原生输出，重复1）</summary>"
                             "<div class='inner'><pre>%s</pre></div></details>"
                             % html.escape(mech[:2500]))
            H.append("</div></details>")
    H.append("</div>")
    open("%s/compare5_report.html" % OUT, "w", encoding="utf-8").write("\n".join(H))
    print("→ %s/compare5_report.html" % OUT)


if __name__ == "__main__":
    main()
