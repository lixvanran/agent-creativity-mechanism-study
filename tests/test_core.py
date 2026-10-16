"""最小回归测试。重点是两条纪律：泄漏检查器可信、选择器是纯函数。"""
import subprocess, sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_leak_checker_catches_known_violation():
    from creativity_lab import leakage
    assert leakage.self_test() is True, "检查器自检失败——不得作为证据使用"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write('x = "请挑出最不寻常且最站得住的一个"\n'); p = f.name
    assert leakage.check(p), "检查器没抓到已知违规"
    os.unlink(p)


def test_clean_file_passes():
    from creativity_lab import leakage
    assert leakage.check("creativity_lab/prompts.py") == []


def test_selector_is_pure_function():
    """选择器必须不依赖 LLM——这是 ToT 式可插拔的核心。"""
    from creativity_lab.gates.base import Select
    s = Select("greedy")
    assert s([0.1, 0.9, 0.5], k=1) == [1]
    s2 = Select("sample", rng=__import__("random").Random(0))
    import random
    s2.rng = random.Random(0)
    for _ in range(5):
        assert len(s2([0.1, 0.9, 0.5], k=1)) == 1


def test_gate_contains_no_content_words():
    """门控/度量模块里不得出现任何题目专有词。"""
    import re
    for mod in ("creativity_lab/gates/base.py", "creativity_lab/metrics.py"):
        src = open(mod, encoding="utf-8").read()
        for bad in ("港澳", "大学", "自行车", "作业", "多血质", "620", "气质量表"):
            assert bad not in src, f"{mod} 里出现了内容词 {bad}"


def test_metrics_on_synthetic():
    import numpy as np
    from creativity_lab import metrics as M
    tight = np.array([[1.0, 0, 0]] * 8) + np.random.RandomState(0).normal(0, .001, (8, 3))
    spread = np.eye(8, 3)[[0, 1, 2, 0, 1, 2, 0, 1]] + np.random.RandomState(1).normal(0, .01, (8, 3))
    assert M.effective_rank(spread) > M.effective_rank(tight) + .5
    assert float(M.spread(spread)) > float(M.spread(tight)) * 2
