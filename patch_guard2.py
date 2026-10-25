import ast

P = '/workspace/lab/creativity_lab/experiments/nested_calibration.py'
lines = open(P, encoding='utf-8').read().split('\n')

# ★ 定位（★ 不猜：★ 按内容找 ★）
i = None
for k, ln in enumerate(lines):
    if '输出目录必须被【显式排除】' in ln:
        i = k
        break
assert i is not None, '★ 定位失败'
# ★ 往前一行是 "# ★★ 防御"，往后到 "continue" 行
start = i - 1
assert '防御' in lines[start], lines[start]
end = start
while 'continue' not in lines[end]:
    end += 1
    assert end - start < 10, '★ 边界异常'
print('替换区间：%d–%d' % (start + 1, end + 1))
for k in range(start, end + 1):
    print('  %d| %s' % (k + 1, lines[k]))

new_block = [
    '        # ★★★ 防御（★ 2026-10-25 三组「把自己的输出当输入」事故的通用预防）',
    '        # ★★★ realpath 级（★ 不是路径字符串相等 ⇒ 挡符号链接 / `../` / 尾斜杠三种绕过）',
    '        try:',
    '            guard_io.assert_output_outside_input_dir(d, OUT_DIR, "nested_calibration")',
    '        except RuntimeError as e:',
    '            print("  ★ 跳过：%s" % e)',
    '            continue',
]
lines[start:end + 1] = new_block
s = '\n'.join(lines)
ast.parse(s)
open(P, 'w', encoding='utf-8').write(s)
print('\n✔ nested_calibration 目录级守卫已换成 realpath 级（★ guard_io）')

# ★ 再补 audit_history 与 family_key_ruler（★ 同样按行定位，不猜锚点）
for fn, marker, imp_after in [
    ('audit_history.py', 'for ds in sorted(os.listdir(HIST)):',
     'from creativity_lab import topics as T          # noqa: E402'),
    ('family_key_ruler.py', 'for pat in ("docs/cmp8/routes/COLLAPSE/eval/runs/dev/anchor_calibration*/calibration.json",',
     None),
]:
    p = '/workspace/lab/creativity_lab/experiments/' + fn
    src = open(p, encoding='utf-8').read()
    if 'guard_io' in src:
        print('  · %s 已含 guard_io ⇒ 跳过' % fn)
        continue
    ls = src.split('\n')
    # ① 加 import：★ 放在 sys.path.insert 那一行之后
    j = None
    for k, ln in enumerate(ls):
        if ln.startswith('sys.path.insert'):
            j = k
            break
    assert j is not None, fn
    ls.insert(j + 1, 'from creativity_lab.experiments import guard_io  # noqa: E402')
    # ② 加守卫
    m = None
    for k, ln in enumerate(ls):
        if marker in ln:
            m = k
            break
    assert m is not None, fn
    if fn == 'audit_history.py':
        guard = ['    # ★★★ 输入/输出隔离（★ 2026-10-25 统一形态：★ 解析输入的同一处就断言，★ realpath 级）',
                 '    guard_io.assert_output_outside_input_dir(HIST, OUT_DIR, "audit_history")']
    else:
        guard = ['    # ★★★ 输入/输出隔离（★ 2026-10-25 统一形态：★ 解析输入的同一处就断言，★ realpath 级）',
                 '    guard_io.assert_output_outside_input_dir(ROOT, os.path.dirname(OUT), "family_key_ruler")']
    ls[m:m] = guard
    out = '\n'.join(ls)
    ast.parse(out)
    open(p, 'w', encoding='utf-8').write(out)
    print('  ✔ %s 目录级守卫已加（★ realpath 级）' % fn)
