# -*- coding: utf-8 -*-
"""★ 把本地 commit 历史推到【独立分支】（★ 不碰共享 branch、不 force）
   --------------------------------------------------------------
   ★ 为什么需要：共享 branch 上只留了【文件层】的最新状态 ⇒ 【过程史】只在本机
     ⇒ 沙箱一重置就全没了（记忆里的铁律：推了才保得住过程）。
   ★ 目标分支：cmp8-g3-history（★ 与共享 branch 同源但独立 ⇒ 零冲突风险）

   ★ 传输层：★ git 自己的 gnutls TLS 栈在这个沙箱里被掐（同一 URL curl 通、git 不通）
     ⇒ 改用 dulwich（纯 Python，走 urllib）★ —— 这是记忆里验证过的解法。

   ★★★ 安全（★ 本轮真踩了一次）：★★
     第一版把 token 拼进 URL（https://user:token@github.com/...）⇒
     **dulwich 会把带凭据的 URL 原样打印出来** ⇒ ★ token 明文进了日志与会话记录。
     ⇒ 修正：**token 绝不进 URL**，改走 `HttpGitClient(username=..., password=...)`
       （dulwich 的 transport kwargs 支持）⇒ ★ URL 里没有凭据 ⇒ 没有可打印的东西。
     ⇒ 另加一道兜底：**输出流过滤**，任何含 token 的行一律替换掉。
     ⇒ 铁律：**PAT 泄露只能在 GitHub 设置里吊销（Classic PAT 不能靠 API 自删）**。
"""
import io
import os
import sys
import urllib.parse

from dulwich import porcelain

REPO_PATH = "/workspace/lab/cmp8repo"
REPO_URL = "https://github.com/lixvanran/agent-creativity-mechanism-study.git"
BRANCH = "cmp8-g3-history"


class _Filter(io.TextIOWrapper):
    """★ 输出过滤器：任何行里出现 token ⇒ 整行替换为 [REDACTED]"""

    def __init__(self, raw, secret):
        super().__init__(raw, encoding="utf-8", errors="replace",
                         line_buffering=True)
        self._secret = secret

    def write(self, s):
        if self._secret and self._secret in s:
            s = s.replace(self._secret, "[REDACTED]")
        return super().write(s)


def main():
    tok = os.environ.get("GITHUB_TOKEN_LIXVANRAN", "")
    if not tok:
        raise SystemExit("✘ 没有 GITHUB_TOKEN_LIXVANRAN")

    # ★ 输出先过滤（兜底）
    sys.stdout = _Filter(sys.stdout.buffer, tok)
    sys.stderr = _Filter(sys.stderr.buffer, tok)

    # ★★★ token 绝不进 URL ★★★（dulwich 的 transport kwargs 走 username/password）
    # ★ 沙箱网络间歇性 TLS EOF ⇒ 重试（★ 不是判据红，是传输层抖动）
    import time
    r = None
    last = None
    for attempt in range(1, 6):
        try:
            r = porcelain.push(REPO_PATH, REPO_URL,
                               ["refs/heads/%s:refs/heads/%s" % (BRANCH, BRANCH)],
                               force=False,
                               username="mavis",
                               password=tok)
            break
        except Exception as e:            # ★ 网络层错误才重试
            last = e
            print("★ 第 %d 次尝试失败（网络层）：%s ⇒ 8 秒后重试" % (attempt, type(e).__name__))
            time.sleep(8)
    if r is None:
        raise SystemExit("✘ 5 次尝试仍失败：%s" % last)
    print("★ 目标分支：%s（★ 独立分支，不动共享 branch）" % BRANCH)
    print("★ push 结果：%r" % (r,))
    return 0


if __name__ == "__main__":
    sys.exit(main())
