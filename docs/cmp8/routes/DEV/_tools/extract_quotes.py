#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从真实页面正文里**抽取** source.quote（连续子串），避免人工转写引入误差。
用法: python3 extract_quotes.py <spec.json> <out.json>
spec.json: [{"key":..., "url":..., "start":<起始锚>, "end":<结束锚>}, ...]
end 为空时取 start 后 200 字；quote = start 锚到 end 锚（含）之间的原样正文。
"""
import json
import re
import subprocess
import sys

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def fetch(url):
    raw = subprocess.run(["curl", "-sL", "--max-time", "35", "--compressed", "-A", UA, url],
                         capture_output=True, timeout=45).stdout
    if not raw:
        return None
    for enc in ("utf-8", "gb18030"):
        try:
            t = raw.decode(enc)
            break
        except Exception:
            t = None
    if t is None:
        return None
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = (t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&quot;", '"').replace("&#39;", "'").replace("&ldquo;", "“").replace("&rdquo;", "”")
          .replace("&#160;", " "))
    for ent in ("&ensp;", "&emsp;", "&thinsp;", "&nbsp;", "&#8201;", "&#8194;", "&#8195;"):
        t = t.replace(ent, " ")
    t = re.sub(r"[ \t\xa0\u2000-\u200a\u3000\u202f]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t


def norm(s):
    return re.sub(r"\s+", "", s)


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    out, bad = {}, []
    for it in spec:
        t = fetch(it["url"])
        if not t:
            print("[FETCH-FAIL] %s %s" % (it["key"], it["url"]))
            bad.append(it["key"])
            continue
        i = t.find(it["start"])
        if i < 0:
            print("[ANCHOR-MISS] %s start=%r" % (it["key"], it["start"]))
            bad.append(it["key"])
            continue
        if it.get("end"):
            j = t.find(it["end"], i)
            if j < 0:
                print("[END-MISS] %s end=%r" % (it["key"], it["end"]))
                bad.append(it["key"])
                continue
            q = t[i:j + len(it["end"])]
        else:
            q = t[i:i + 200]
        q = re.sub(r"\s+", " ", q).strip()
        if "�" in q:
            print("[MOJIBAKE] %s" % it["key"])
            bad.append(it["key"])
            continue
        ok = norm(q) in norm(t)
        print("[%s] %s  (len=%d, norm_hit=%s)\n    %s" % (it["key"], it["url"], len(q), ok, q))
        if not ok:
            bad.append(it["key"])
        out[it["key"]] = q
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n提取成功 %d/%d；失败: %s" % (len(out), len(spec), bad or "无"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
