#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取本次引用页面的**真实正文**（保留原始全角标点），用于核对 source.quote 是否为页面中的连续子串。
用法: python3 fetch_quotes.py <spec.json>
spec.json: [{"id":..., "url":..., "phrases":[...]}]
"""
import json
import re
import subprocess
import sys

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def fetch(url):
    try:
        raw = subprocess.run(
            ["curl", "-sL", "--max-time", "35", "--compressed", "-A", UA, url],
            capture_output=True, timeout=45).stdout
    except Exception as e:
        return None, "curl error: %s" % e
    if not raw:
        return None, "empty response"
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            t = raw.decode(enc)
            break
        except Exception:
            t = None
    if t is None:
        return None, "decode failed"
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    t = t.replace("&quot;", '"').replace("&#39;", "'").replace("&ldquo;", "“").replace("&rdquo;", "”")
    t = re.sub(r"[ \t\xa0　]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t, None


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    for item in spec:
        t, err = fetch(item["url"])
        print("=" * 100)
        print("[%s] %s" % (item["id"], item["url"]))
        if err:
            print("  !! FETCH FAILED:", err)
            continue
        for ph in item.get("phrases", []):
            i = t.find(ph)
            if i < 0:
                print("  [MISS] %r" % ph)
                continue
            s = t[max(0, i - 10): i + len(ph) + 150]
            print("  [HIT ] %r" % ph)
            print("        ...%s..." % s.replace("\n", " "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
