"""无 pytest 依赖的测试运行器（沙箱 pip 不通）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib.util
spec = importlib.util.spec_from_file_location("t", os.path.join(os.path.dirname(__file__), "test_core.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
fns = [getattr(m, n) for n in dir(m) if n.startswith("test_")]
ok = 0
for fn in fns:
    try:
        fn(); print(f"  ✓ {fn.__name__}"); ok += 1
    except Exception as e:
        print(f"  ✗ {fn.__name__}: {e}")
print(f"\n{ok}/{len(fns)} 通过")
sys.exit(0 if ok == len(fns) else 1)
