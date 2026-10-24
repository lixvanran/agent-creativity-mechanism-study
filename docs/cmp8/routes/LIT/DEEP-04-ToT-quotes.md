# DEEP-04 · Tree of Thoughts 逐字摘录（可溯源）

> 任务：把 ToT（arXiv 2305.10601）+ `princeton-nlp/tree-of-thought-llm` 里可抄的机制逐字摘出来。
> 本文件只放**逐字引文 + 位置**；推论与规格在 `DEEP-04-ToT-spec.md`。

---

## 0. 溯源元信息（全部本人核验）

| 对象 | 核验结果 | 核验方式 |
|---|---|---|
| arXiv ID | `2305.10601` | `export.arxiv.org/api/query?id_list=2305.10601` |
| 标题 | `Tree of Thoughts: Deliberate Problem Solving with Large Language Models` | arXiv API `<entry><title>` |
| 版本 | `v2`，`<updated>2023-12-03T22:50:35Z`，`<published>2023-05-17T23:16:17Z` | arXiv API |
| 作者（v2） | Shunyu Yao, Dian Yu, Jeffrey Zhao, Izhak Shafran, Thomas L. Griffiths, Yuan Cao, Karthik Narasimhan | arXiv API `<author><name>` |
| arXiv comment | `NeurIPS 2023 camera ready version. Code repo with all prompts: https://github.com/princeton-nlp/tree-of-thought-llm` | arXiv API `<arxiv:comment>` |
| 主分类 | `cs.CL`（cs.AI / cs.LG 并列） | arXiv API `<category>` |
| 仓库 | `princeton-nlp/tree-of-thought-llm`，HEAD = `8050e67d0e3a0fddc424d7fa5801538722a4c4cc`（2025-01-16，"Merge pull request #70 from ltn18/gpt4o"），MIT | `git clone` + `git log -1` |
| 论文全文 | `arxiv.org/html/2305.10601v2`（LaTeXML 187,762 B）**数学被剥离** → 改用 `ar5iv.labs.arxiv.org/html/2305.10601`（171,182 B，含 MathML `alttext`）**并**用 PDF `arxiv.org/pdf/2305.10601v2`（799,685 B，`pdftotext -layout`）双路交叉 | 实测 |
| 图表源文件 | arXiv e-print 源码包 `https://arxiv.org/e-print/2305.10601v2`（637,671 B）内含 `figures/game24_scale.pdf` = **Figure 3(a)** | 解包实测 |

> 标签核对结论：**2305.10601 = Tree of Thoughts**（Yao et al., NeurIPS 2023），标签无误。
> ⚠️ 但 v2 的作者名单与 v1 不同（v2 删去了 Yuandong Tian / Izhak Golubnechik / Abishek Sridhar 等）。引用作者时请用上面这一串。

---

## 1. 提示词全文（代码，可直接抄）

### 1.1 `value_prompt`（Game of 24，主评估器）— `src/tot/prompts/game24.py:66-105`

```python
value_prompt = '''Evaluate if given numbers can reach 24 (sure/likely/impossible)
10 14
10 + 14 = 24
sure
11 12
11 + 12 = 23
12 - 11 = 1
11 * 12 = 132
11 / 12 = 0.91
impossible
4 4 10
4 + 4 + 10 = 8 + 10 = 18
4 * 10 - 4 = 40 - 4 = 36
(10 - 4) * 4 = 6 * 4 = 24
sure
4 9 11
9 + 11 + 4 = 20 + 4 = 24
sure
5 7 8
5 + 7 + 8 = 12 + 8 = 20
(8 - 5) * 7 = 3 * 7 = 21
I cannot obtain 24 now, but numbers are within a reasonable range
likely
5 6 6
5 + 6 + 6 = 17
(6 - 5) * 6 = 1 * 6 = 6
I cannot obtain 24 now, but numbers are within a reasonable range
likely
10 10 11
10 + 10 + 11 = 31
(11 - 10) * 10 = 10
10 10 10 are all too big
impossible
1 3 3
1 * 3 * 3 = 9
(1 + 3) * 3 = 12
1 3 3 are all too small
impossible
{input}
'''
```

⚠️ **代码里是 `sure/likely/impossible`（`likely`），论文正文写的是 `sure/maybe/impossible`（`maybe`）。**
→ 论文 p.6 原文：`we prompt LM to evaluate each thought candidate as "sure/maybe/impossible" with regard to reaching 24.`
→ 抄的时候**以代码为准**（`likely`），因为 `value_map` 的键是 `likely`（见 §3.1）。

### 1.2 `value_last_step_prompt`（Game of 24 末步判定）— `src/tot/prompts/game24.py:107-134`

```python
value_last_step_prompt = '''Use numbers and basic arithmetic operations (+ - * /) to obtain 24. Given an input and an answer, give a judgement (sure/impossible) if the answer is correct, i.e. it uses each input exactly once and no other numbers, and reach 24.
Input: 4 4 6 8
Answer: (4 + 8) * (6 - 4) = 24
Judge: 
sure
Input: 2 9 10 12
Answer: 2 * 12 * (10 - 9) = 24
Judge: 
sure
Input: 4 9 10 13
Answer: (13 - 9) * (10 - 4) = 24
Judge: 
sure
Input: 4 4 6 8
Answer: (4 + 8) * (6 - 4) + 1 = 25
Judge: 
impossible
Input: 2 9 10 12
Answer: 2 * (12 - 10) = 24
Judge: 
impossible
Input: 4 9 10 13
Answer: (13 - 4) * (10 - 9) = 24
Judge: 
impossible
Input: {input}
Answer: {answer}
Judge:'''
```

### 1.3 `propose_prompt`（Game of 24 思路生成）— `src/tot/prompts/game24.py:52-64`

```python
propose_prompt = '''Input: 2 8 8 14
Possible next steps:
2 + 8 = 10 (left: 8 10 14)
8 / 2 = 4 (left: 4 8 14)
14 + 2 = 16 (left: 8 8 16)
2 * 8 = 16 (left: 8 14 16)
8 - 2 = 6 (left: 6 8 14)
14 -  2 = 7 (left: 7 8 8)
14 - 2 = 12 (left: 8 8 12)
Input: {input}
Possible next steps:
'''
```

论文 p.6 对应句：`The same "propose prompt" is used for all 3 thought steps, though it only has one example with 4 input numbers.`

### 1.4 `vote_prompt`（Creative Writing，投票评估器）— `src/tot/prompts/text.py:18-19`

```python
vote_prompt = '''Given an instruction and several choices, decide which choice is most promising. Analyze each choice in detail, then conclude in the last line "The best choice is {s}", where s the integer id of the choice.
'''
```

⚠️ **`{s}` 从未被 `.format()`**（`src/tot/tasks/text.py:60-66` 只做字符串拼接），模型看到的是字面量 `"The best choice is {s}"`。
⚠️ 论文 p.6 的**转述**与代码原文不一致：
> 论文：`A simple zero-shot vote prompt ("analyze choices below, then conclude which is most promising for the instruction") is used to sample 5 votes at both steps.`
> 代码原文见上。**以代码为准**。

### 1.5 `value_prompt`（Crosswords，DFS 剪枝用）— `src/tot/prompts/crosswords.py:278-326`

```python
value_prompt = '''Evaluate if there exists a five letter word of some meaning that fit some letter constraints (sure/maybe/impossible).

Incorrect; to injure: w _ o _ g
The letter constraint is: 5 letters, letter 1 is w, letter 3 is o, letter 5 is g.
Some possible words that mean "Incorrect; to injure":
wrong (w r o n g): 5 letters, letter 1 is w, letter 3 is o, letter 5 is g. fit!
sure
...
I cannot think of any words now. 3 letters are constrained, and it is extremely unlikely to have a word with pattern _ d _ w f to mean "An inn"
impossible

{input}
'''
```
（完整 8 条示例见文件 `src/tot/prompts/crosswords.py:278-326`；本任务只用到它的**输出标签集合** `{sure, maybe, impossible}` 与"最后一行是标签"的结构。）

### 1.6 `propose_prompt`（Crosswords，带置信度）— `src/tot/prompts/crosswords.py:270-275`

```python
propose_prompt = '''Let's play a 5 x 5 mini crossword, where each word should have exactly 5 letters.

{input}

Given the current status, list all possible answers for unfilled or changed words, and your confidence levels (certain/high/medium/low), using the format "h1. apple (medium)". Use "certain" cautiously and only when you are 100% sure this is the correct word. You can list more then one possible answer for each word.
'''
```

### 1.7 `score_prompt` / `compare_prompt`（Creative Writing 判分）— `src/tot/prompts/text.py:21-25`

```python
compare_prompt = '''Briefly analyze the coherency of the following two passages. Conclude in the last line "The more coherent passage is 1", "The more coherent passage is 2", or "The two passages are similarly coherent".
'''

score_prompt = '''Analyze the following passage, then at the last line conclude "Thus the coherency score is {s}", where s is an integer from 1 to 10.
'''
```
⚠️ `score_prompt` 里的 `{s}` **同样从未 format**（`src/tot/tasks/text.py:34`：`prompt = score_prompt + output`），而解析正则 `r".*coherency score is (\d+).*"` 仍能工作（模型会自己填数字）。
⚠️ 判分失败**静默当 0 分**（`src/tot/tasks/text.py:48`：`'r': sum(scores) / len(scores) if scores else 0`）—— 解析失败的样本既不计入 `scores`，也不告警，只在 `:45` 打一行 print。

---

## 2. 状态表示与拼接（可抄的"离散化"机制）

### 2.1 论文定义 — PDF p.3（`main.tex:368`）

> `ToT frames any problem as a search over a tree, where each node is a \textbf{state} $s = [x, z_{1 \cdots i}]$ representing a partial solution with the input and the sequence of thoughts so far.`

### 2.2 代码：state 就是**一个字符串**，子节点 = 父串 + 新思路 + `\n`

`src/tot/methods/bfs.py:34-37`：
```python
def get_proposals(task, x, y): 
    propose_prompt = task.propose_prompt_wrap(x, y)
    proposals = gpt(propose_prompt, n=1, stop=None)[0].split('\n')
    return [y + _ + '\n' for _ in proposals]
```

`src/tot/methods/bfs.py:39-47`：
```python
def get_samples(task, x, y, n_generate_sample, prompt_sample, stop):
    if prompt_sample == 'standard':
        prompt = task.standard_prompt_wrap(x, y)
    elif prompt_sample == 'cot':
        prompt = task.cot_prompt_wrap(x, y)
    else:
        raise ValueError(f'prompt_sample {prompt_sample} not recognized')
    samples = gpt(prompt, n=n_generate_sample, stop=stop)
    return [y + _ for _ in samples]
```

⇒ **两种拼接格式**：
- `propose` 模式（Game of 24 / Crosswords）：`child = parent + thought_line + "\n"`（thought_line 是 `split('\n')` 后的一行，**不带**换行符，再补回 `\n`）。
- `sample` 模式（Creative Writing）：`child = parent + continuation`（continuation 直接是 API 返回文本；step0 的 `stop='\nPassage:\n'` 把 plan 截断）。

### 2.3 **状态投影**（把路径压成可枚举键）——这是最值得抄的一零件

`src/tot/tasks/game24.py:9-11`：
```python
def get_current_numbers(y: str) -> str:
    last_line = y.strip().split('\n')[-1]
    return last_line.split('left: ')[-1].split(')')[0]
```

`src/tot/tasks/game24.py:66-73`：
```python
    @staticmethod
    def propose_prompt_wrap(x: str, y: str) -> str:
        current_numbers = get_current_numbers(y if y else x)
        if current_numbers == '24':
            prompt = cot_prompt.format(input=x) + 'Steps:' + y
            # print([prompt])
        else:
            prompt = propose_prompt.format(input=current_numbers)
        return prompt
```

`src/tot/tasks/game24.py:75-83`：
```python
    @staticmethod
    def value_prompt_wrap(x: str, y: str) -> str:
        last_line = y.strip().split('\n')[-1]
        if 'left: ' not in last_line:  # last step
            ans = last_line.lower().replace('answer: ', '')
            # print([value_last_step_prompt.format(input=x, answer=ans)])
            return value_last_step_prompt.format(input=x, answer=ans)
        current_numbers = get_current_numbers(y)
        return value_prompt.format(input=current_numbers)
```

⇒ **评估器只看状态投影（Game of 24 = 剩余数字多重集），不看路径**。`value_cache` 以 `value_prompt` 字符串为键 ⇒ 相同投影的状态共享同一个分（`src/tot/methods/bfs.py:6-14`）：
```python
def get_value(task, x, y, n_evaluate_sample, cache_value=True):
    value_prompt = task.value_prompt_wrap(x, y)
    if cache_value and value_prompt in task.value_cache:
        return task.value_cache[value_prompt]
    value_outputs = gpt(value_prompt, n=n_evaluate_sample, stop=None)
    value = task.value_outputs_unwrap(x, y, value_outputs)
    if cache_value:
        task.value_cache[value_prompt] = value
    return value
```

### 2.4 搜索循环（无早停、固定步数）— `src/tot/methods/bfs.py:49-88`

```python
def solve(args, task, idx, to_print=True):
    global gpt
    gpt = partial(gpt, model=args.backend, temperature=args.temperature)
    print(gpt)
    x = task.get_input(idx)  # input
    ys = ['']  # current output candidates
    infos = []
    for step in range(task.steps):
        # generation
        if args.method_generate == 'sample':
            new_ys = [get_samples(task, x, y, args.n_generate_sample, prompt_sample=args.prompt_sample, stop=task.stops[step]) for y in ys]
        elif args.method_generate == 'propose':
            new_ys = [get_proposals(task, x, y) for y in ys]
        new_ys = list(itertools.chain(*new_ys))
        ids = list(range(len(new_ys)))
        # evaluation
        if args.method_evaluate == 'vote':
            values = get_votes(task, x, new_ys, args.n_evaluate_sample)
        elif args.method_evaluate == 'value':
            values = get_values(task, x, new_ys, args.n_evaluate_sample)

        # selection
        if args.method_select == 'sample':
            ps = np.array(values) / sum(values)
            select_ids = np.random.choice(ids, size=args.n_select_sample, p=ps).tolist()
        elif args.method_select == 'greedy':
            select_ids = sorted(ids, key=lambda x: values[x], reverse=True)[:args.n_select_sample]
        select_new_ys = [new_ys[select_id] for select_id in select_ids]
        ...
        infos.append({'step': step, 'x': x, 'ys': ys, 'new_ys': new_ys, 'values': values, 'select_new_ys': select_new_ys})
        ys = select_new_ys
```

固定步数来自各 task：`src/tot/tasks/game24.py:35` `self.steps = 4`；`src/tot/tasks/text.py:23-24` `self.steps = 2` / `self.stops = ['\nPassage:\n', None]`；`src/tot/tasks/crosswords.py:172` `self.steps = 10  # TODO: variable steps??`。

---

## 3. value 评估器：取值表、解析、失败处理

### 3.1 `value_map` 与 `# TODO: ad hoc` — `src/tot/tasks/game24.py:85-92`（逐字）

```python
    @staticmethod
    def value_outputs_unwrap(x: str, y: str, value_outputs: list) -> float:
        if len(y.strip().split('\n')) == 4 and 'answer' not in y.lower():
            return 0
        value_names = [_.split('\n')[-1] for _ in value_outputs]
        value_map = {'impossible': 0.001, 'likely': 1, 'sure': 20}  # TODO: ad hoc
        value = sum(value * value_names.count(name) for name, value in value_map.items())
        return value
```

⇒ 三处 ad-hoc（**逐条对应 spec §7**）：
1. `value_map = {'impossible': 0.001, 'likely': 1, 'sure': 20}  # TODO: ad hoc` —— 数值比例 0.001 : 1 : 20 纯手工。
2. 标签靠 `_.split('\n')[-1]` **取最后一行原文**做**精确字符串相等**匹配（`value_names.count(name)`）——解析失败 ⇒ 该样本贡献 0，且不报错、不计数。
3. `if len(y.strip().split('\n')) == 4 and 'answer' not in y.lower(): return 0` —— 硬编码"4 行"结构断言。

### 3.2 Crosswords 的第二个 ad-hoc 取值表 — `src/tot/tasks/crosswords.py:220-239`

```python
    def propose_outputs_unwrap(self, x: str, y: str, outputs: list, n_max_propose: int) -> list:
        confidence_to_value = {'certain': 1, 'high': 0.5, 'medium': 0.2, 'low': 0.1}  # TODO: ad hoc
        proposals_to_scores = {}
        for output in outputs:
            lines = output.split('\n')
            pattern = r'^([hv][1-5])\. ([a-zA-Z]{5,5}) \((certain|high|medium|low)\).*$'
            for line in lines:
                match = re.match(pattern, line)
                if match:
                    parts = [match.group(1), match.group(2), match.group(3)]
                    proposal = parts[0].lower() + '. ' + parts[1].lower()
                    score = confidence_to_value.get(parts[2], 0)
                    proposals_to_scores[proposal] = proposals_to_scores.get(proposal, 0) + score
        
        proposals = sorted(proposals_to_scores.items(), key=lambda x: x[1], reverse=True)
        if n_max_propose != -1:
            proposals = proposals[:n_max_propose]
        proposals = [y + proposal[0] + '\n' for proposal in proposals]
        self.cache_proposals[(x, y, n_max_propose)] = proposals
        return proposals
```
（`confidence_to_value` 那一行在 `src/tot/tasks/crosswords.py:221`；`score = ...` 在 `:231`。）

`src/tot/tasks/crosswords.py:241-257`：
```python
    def evaluate(self, x: str, y: str, n_evaluate_sample: int) -> int:
        self.set_status(x, y)
        assert n_evaluate_sample == 1 # TODO: ad hoc
        count = {'sure': 0, 'maybe': 0, 'impossible': 0}
        for ans, data, status in zip(self.env.ans, self.env.data, self.env.status):
            if ans.count('_') >= 4: continue
            ans = ' '.join(ans.lower())
            line = f'{data}: {ans}'
            prompt = value_prompt.format(input=line)
            res = gpt(prompt)[0]
            ...
            res = res.split('\n')[-1].strip()
            if res in count: count[res] += 1
        print(count)
        return count
```

### 3.3 vote 解析（Creative Writing）— `src/tot/tasks/text.py:59-80`

```python
    @staticmethod
    def vote_prompt_wrap(x: str, ys: list) -> str:
        prompt = vote_prompt
        for i, y in enumerate(ys, 1):
            # y = y.replace('Plan:\n', '')
            # TODO: truncate the plan part?
            prompt += f'Choice {i}:\n{y}\n'
        return prompt
    
    @staticmethod
    def vote_outputs_unwrap(vote_outputs: list, n_candidates: int) -> list:
        vote_results = [0] * n_candidates
        for vote_output in vote_outputs:
            pattern = r".*best choice is .*(\d+).*"
            match = re.match(pattern, vote_output, re.DOTALL)
            if match:
                vote = int(match.groups()[0]) - 1
                if vote in range(n_candidates):
                    vote_results[vote] += 1
            else:
                print(f'vote no match: {[vote_output]}')
        return vote_results
```

⚠️ 两处静默失效：
- `.*(\d+).*` 贪婪 ⇒ 抓的是**输出里最后一个数字**，不是 "best choice is" 后面的那个。
- 越界票（`vote not in range(n_candidates)`）**直接丢弃**，不计入任何候选，也不报错。

---

## 4. 剪枝 / 停止

### 4.1 论文里的 `v_th`（**只存在于论文，代码里没有**）

PDF p.4，Algorithm 1 & 2（`main.tex:423-458`）逐字：

```
Algorithm 1 ToT-BFS(x, pθ , G, k, V, T, b)
Require Input x, LM pθ , thought generator G() & size limit k, states evaluator V(), step limit T, breadth limit b.
S0 ← { x }
for t = 1, · · · , T do
    S′t ← { [s, z] | s ∈ St−1, zt ∈ G(pθ , s, k) }      ▷ Generate thoughts
    Vt ← V(pθ , S′t )                                    ▷ Evaluate thoughts
    St ← arg maxS⊂S′t,|S|=b Σs∈S Vt(s)                   ▷ Prune thoughts
return G(pθ , arg maxs∈ST VT (s), 1)

Algorithm 2 ToT-DFS(s, t, pθ , G, k, V, T, vth )
Require Current state s, step t, LM pθ , thought generator G() and size limit k, states evaluator V(), step limit T, threshold vth
if t > T then
    record output G(pθ , s, 1)
for s′ ∈ G(pθ , s, k) do                               ▷ sorted candidates
    if V(pθ , {s′})(s) > vth then                       ▷ pruning
        DFS(s′ , t + 1)
```

PDF p.4 正文（`main.tex:240`）：
> `(b) Depth-first search (DFS) (Algorithm 2) explores the most promising state first, until the final output is reached ($t>T$), or the state evaluator deems it impossible to solve the problem from the current $s$ ($V(p_{\theta},\{s\})(s)\leq v_{th}$ for a value threshold $v_{th}$). In the latter case, the subtree from $s$ is pruned to trade exploration for exploitation. In both cases, DFS backtracks to the parent state of $s$ to continue exploration.`

⚠️ **论文自身的不一致**：Algorithm 2 里写 `V(pθ,{s′})(s) > vth`（求值的是**父状态 s**），正文写 `V(pθ,{s})(s) ≤ vth`（求值的是**当前 s**）。两处不等价。**照抄伪代码会抄错。**

### 4.2 ⚠️ **官方仓库里根本没有 `v_th` 这个变量**

本人对仓库**完整历史**核查（`git fetch --unshallow` 后共 **50 个 commit**，`git grep -n "v_th" $(git rev-list --all)` + 工作树全文件含 `.ipynb`）：
```
$ git rev-list --all --count
50
$ git grep -n "v_th" $(git rev-list --all) | wc -l
0
$ grep -rn "v_th" . --include=*      # 工作树
（无输出）
```
⇒ **`v_th` 是论文概念，代码从未实现 —— 在全部 50 个历史 commit 中一次都没出现过。**
⇒ HEAD 里 `# TODO: ad hoc` 共 **3 处**（另 1 处在 notebook 里，是 `crosswords.py:221` 的重复）：
```
src/tot/tasks/game24.py:90:        value_map = {'impossible': 0.001, 'likely': 1, 'sure': 20}  # TODO: ad hoc
src/tot/tasks/crosswords.py:221:        confidence_to_value = {'certain': 1, 'high': 0.5, 'medium': 0.2, 'low': 0.1}  # TODO: ad hoc
src/tot/tasks/crosswords.py:243:        assert n_evaluate_sample == 1 # TODO: ad hoc
```
（另：`src/tot/tasks/crosswords.py:172` `self.steps = 10  # TODO: variable steps??`。
历史里同样的 3 处曾位于仓库根目录的 `tasks/game24.py:90` / `tasks/crosswords.py:220,242`（`src/` 重构之前）—— **数量从未变过**。）

### 4.3 代码里**实际实现**的剪枝：Crosswords DFS（notebook）

`scripts/crosswords/search_crosswords-dfs.ipynb`，cell 7（逐字）：
```python
def dfs(env, actions, infos, time_limit, prune, max_per_state):
    # get candidate thoughts
    candidates_to_scores = get_candidates_to_scores(env)
    if len(candidates_to_scores) == 0: return 0, [], []

    # back up current state
    board, status, steps = env.board.copy(), env.status.copy(), env.steps

    # try each candidate
    cnt_per_state = 0
    for action in sorted(candidates_to_scores, key=candidates_to_scores.get, reverse=True):
        obs, r, done, info = env.step(action)
        r = info['r_word']
        if len(infos) < time_limit and env.steps < 10 and not any(_ == 2 for _ in env.status):  # not violating any existing constraints
            cnt_per_state += 1
            if cnt_per_state > max_per_state: break
            count = env.prompt_status()       
            actions.append(action)  
            ...
            info = {'total_step': len(infos), 'env_step': env.steps, 'actions': actions.copy(), 'info': info, 'count': count}
            infos.append(info)
            if not prune or count['impossible'] < 1:  # only continue if the current status is possible
                dfs(env, actions, infos, time_limit, prune, max_per_state)
            actions.pop()
        env.reset(env.idx, board=board.copy(), status=status.copy(), steps=steps)
```
cell 8 / cell 9（调用参数）：
```python
    dfs(env, actions, infos, 100, prune=True, max_per_state=3)    # → logs/crosswords/infoss_dfs_prune.json
    dfs(env, actions, infos, 100, prune=False, max_per_state=3)   # → logs/crosswords/infoss_dfs_no_prune.json
```

⇒ **实际剪枝规则 = "任一剩余线索被判 `impossible` ⇒ 剪掉整棵子树"**（`count['impossible'] < 1`），**不是** value 阈值。
⇒ DFS 的三重上限：`time_limit=100`（总状态数）、`env.steps < 10`（单条路径深度）、`max_per_state=3`（每个状态最多扩展 3 个子）。
⇒ **没有任何早停**：找到解也继续跑满。

### 4.4 论文自己承认 BFS 没有早停 — PDF p.14（Appendix B.3）

> `• There is much space for improving efficiency, e.g., BFS could early stop when solution is found, or trim down beam size to when some thoughts are "impossible".`

### 4.5 BFS vs DFS 实现差异总表

| 维度 | BFS（`src/tot/methods/bfs.py`） | DFS（notebook cell 7） |
|---|---|---|
| 状态容器 | `ys` 列表，每步保留 `n_select_sample`(=b) 个 | `env`（可深拷贝回溯）+ `infos` 列表 |
| 生成方式 | 每个父状态各调一次 `gpt()` | 每个状态调 `get_candidates_to_scores(env)`（`n=8` 次采样聚合） |
| 评估方式 | 逐状态 `get_value` / `get_votes` | 逐线索 `env.prompt_status()`，返回 `{sure, maybe, impossible}` 计数 |
| 剪枝 | 无（只按 value 排序取 top-b） | `count['impossible'] < 1` ⇒ 剪子树 |
| 回溯 | 无 | `env.reset(env.idx, board=..., status=..., steps=...)` |
| 停止 | 固定 `range(task.steps)` | `time_limit=100` / `env.steps<10` / `max_per_state=3` |
| 输出 | 最后一步保留的 b 个候选（**全部返回**） | "render the deepest explored state (the first explored one if multiple)" |

论文 p.7 对 DFS 输出的描述：
> `We limit DFS search steps to 100, and simply render the deepest explored state (the first explored one if multiple) into the final output.`

---

## 5. best-of-k 对照：论文 Fig 3(a) 的**精确数值**（我从矢量图里解出来的）

### 5.1 论文对"同一根轴"的定义（逐字）

PDF p.6：
> `We also consider an oracle setup for IO/CoT, by calculating the success rate using best of k samples (1 ≤ k ≤ 100). To compare IO/CoT (best of k) with ToT, we consider calculating the tree nodes visited per task in ToT across b=1···5, and map the 5 success rates in Figure 3(a), treating IO/CoT (best of k) as visiting k nodes in a bandit. Not surprisingly, CoT scales better than IO, and best of 100 CoT samples achieve a success rate of 49%, but still much worse than exploring more nodes in ToT (b>1).`

### 5.2 Fig 3(a) 的矢量数据（`figures/game24_scale.pdf`，arXiv 源码包内）

**提取方法**：`qpdf --qdf` 展平 → 解压内容流 → 解析 `m`/`l` 路径算子 → 用网格线坐标标定。
标定参数（从同文件内容流直接读出）：
- 竖网格线 x = `54.196, 105.450, 156.704, 207.958, 259.212` ⇒ 依次为 **0, 25, 50, 75, 100**（节点数）
- 横网格线 y = `94.156, 149.433, 204.711` ⇒ 依次为 **0.2, 0.4, 0.6**（成功率）
- `x_data = (px − 54.196) / (259.212 − 54.196) × 100`
- `y_data = (py − 40.348) / 276.385`（`40.348` = 0 基线，由蓝色 IO 曲线端点 + 橙色 CoT 曲线端点双向验证）

**三条曲线的原始路径**：
```
IO   (best of k) 蓝, 100 点: x 56.25→259.21 , y 59.17→130.09
CoT  (best of k) 橙, 100 点: x 56.25→259.21 , y 50.02→174.31
ToT  (b=1…5)    绿,  5 点: (95.278,162.976) (118.466,198.077) (141.729,218.806)
                        (165.367,232.349) (190.203,243.405)
```

**换算成数据坐标**（标定后）：

| 曲线 | 点 | 节点数 x | 成功率 y | 与论文正文对照 |
|---|---|---|---|---|
| ToT | b=1 | **20.0** | **0.444** | 正文 45% ✓ |
| ToT | b=2 | **31.3** | **0.571** | — |
| ToT | b=3 | **42.7** | **0.646** | — |
| ToT | b=4 | **54.2** | **0.695** | — |
| ToT | b=5 | **66.3** | **0.735** | 正文 74% ✓ |
| IO (best of k) | k=1 | 1.0 | 0.068 | 表 2: IO 7.3% ✓ |
| IO (best of k) | k=100 | 100.0 | 0.325 | 表 2: IO(best of 100) 33% ✓ |
| CoT (best of k) | k=1 | 1.0 | 0.035 | 表 2: CoT 4.0% ✓ |
| CoT (best of k) | k=100 | 100.0 | 0.485 | 表 2: CoT(best of 100) 49% ✓ |

⇒ 六个独立端点全部与正文表格吻合（误差 <1.5pp），标定可信。

---

## 6. 成本表（逐字）

PDF p.14，Table 7：
```
            Game of 24            Generate/Prompt tokens       Cost per case     Success
            IO (best of 100)      1.8k / 1.0k                 $0.13              33%
            CoT (best of 100)     6.7k / 2.2k                 $0.47              49%
            ToT                   5.5k / 1.4k                 $0.74              74%
                                Table 7: Cost analysis on Game of 24.
```
PDF p.14，Table 8：
```
                 Creative Writing      Generate/Prompt tokens        Cost per case
                 IO                     0.9k / 0.4k                 $0.06
                 CoT                    0.9k / 0.4k                 $0.07
                 ToT                    4k / 2.9k                   $0.32
                                Table 8: Cost analysis on Game of 24.
```
（表 8 的 caption 原文就是 "Cost analysis on Game of 24." —— **原文笔误**，实为 Creative Writing。）

PDF p.14 正文：
> `Running ToT requires significantly more computations than IO or CoT prompting. For example, in Game of 24 (Table 7 below), solving a problem with ToT requires 5.5k completion tokens, close to 100 CoT trials (6.7k tokens). But the performance of ToT is better than best of 100 independent CoT trials.`
> `On Creative Writing (Table 8 below), we found ToT takes around 5x completion tokens and money cost, which is intuitive as b = 5 and most tokens are generated passages.`
> `So completing Game of 24 and Creative Writing's main ToT experiments cost around 0.74 × 100 + 0.32 × 100 = 106 dollars.`

### 6.1 定价公式（代码里）— `src/tot/models.py:39-47`
```python
def gpt_usage(backend="gpt-4"):
    global completion_tokens, prompt_tokens
    if backend == "gpt-4":
        cost = completion_tokens / 1000 * 0.06 + prompt_tokens / 1000 * 0.03
    elif backend == "gpt-3.5-turbo":
        cost = completion_tokens / 1000 * 0.002 + prompt_tokens / 1000 * 0.0015
    elif backend == "gpt-4o":
        cost = completion_tokens / 1000 * 0.00250 + prompt_tokens / 1000 * 0.01
    return {"completion_tokens": completion_tokens, "prompt_tokens": prompt_tokens, "cost": cost}
```
⚠️ `backend` 若不在三者之一，`cost` **未定义 ⇒ NameError**。

---

## 7. ⚠️ 我用官方仓库发布日志反算的结果（本人实测，非转述）

仓库 `logs/` 里发布了 6 个 run 的完整日志。我用 `run.py` 的原始口径重算：

| 方法 | 论文/表 2 | **日志实测** | 结论 |
|---|---|---|---|
| IO avg-of-100 | 7.3% | **7.34%** | ✓ 复现 |
| IO best-of-100 | 33% | **33%** | ✓ 复现 |
| CoT avg-of-100 | 4.0% | **4.03%** | ✓ 复现 |
| CoT best-of-100 | 49% | **49%** | ✓ 复现 |
| **ToT b=5** | **74%** | **69.0%（any-of-5）/ 23.8%（avg-of-5）** | ✗ **差 5pp** |
| IO 成本/例 | 1.8k / 1.0k, $0.13 | **1800 completion / 1000 prompt, $0.138** | ✓ 完全复现 |
| CoT 成本/例 | 6.7k / 2.2k, $0.47 | **4619 completion / 1486 prompt, $0.322** | ✗ **发布日志不是表 7 那一跑** |
| ToT 成本/例 | 5.5k / 1.4k, $0.74 | **5479 completion / 13,879 prompt, $0.745** | ✗ **prompt 那一格差 ~10×** |

**三个必须记住的推论**：
1. **表 7 的 ToT prompt 格 "1.4k" 与它自己的 "$0.74" 互相矛盾**：$0.74 只有在 prompt ≈ **13.9k** 时才成立（5479/1000×0.06 + 13879/1000×0.03 = 0.3287 + 0.4164 = $0.745）。发布日志的 `prompt_tokens` 末值 = **1,387,936 / 100 例 = 13,879**。⇒ **表 7 的 ToT prompt token 数应读作 13.9k，印错了**。
2. **发布日志的 b=5 ToT 只到 69.0%（any-of-5），不是 74%**。引用 "74%" 时要标清楚它来自论文正文而非发布产物。
3. **Creative Writing 的 ToT 7.56 无法从发布日志复现**：`logs/text/gpt-4_1.0_generate_sample_select_greedy_sample5_*.json` 里 100 个任务的 `accs` **全是 0**（连分数都没存）。而 IO 6.19 / CoT 6.93 我能**精确复现**（各 1000 个分数的均值 = 6.19 / 6.93）。

### 7.1 "节点数"从发布日志反算（用来核对 Fig 3(a) 的 x 轴定义）

`logs/game24/gpt-4_0.7_propose1_value3_greedy5_start900_end1000.json`，100 题，每题：

| 候选定义 | 均值 | 与 Fig 3(a) 的 66.3 比 |
|---|---|---|
| 生成的想法总数 `Σ len(new_ys)` | 84.1 | 偏大 27% |
| 被打分的状态数（含重复） | 84.1 | 偏大 |
| **去重后的不同状态数（= 状态投影去重）** | **70.1**（中位 70.5） | **最接近 66.3（差 5.7%）** |
| 保留的节点数（root + 每步 top-b） | 21.0 | 偏小 |

⇒ **Fig 3(a) 的 "tree nodes visited" 最可能就是"被评估过的不同状态数"（按状态投影去重）**。发布日志给 70.1，论文画 66.3，差 5.7% —— 与发布日志本身不是论文那一跑（见 §7）一致。

### 7.2 发布的 DFS 日志（Crosswords）

| 日志 | 状态总数 / 20 局 | 每局均值 | 触顶情况 |
|---|---|---|---|
| `logs/crosswords/infoss_dfs_prune.json` | 1856 | **92.8** | 8 局跑满 100 步上限 |
| `logs/crosswords/infoss_dfs_no_prune.json` | 2000 | **100.0** | **20/20 局全部跑满 `time_limit=100`** |

⇒ 剪枝版平均少访问 7.2 个状态/局，但**没有一局因此提前收工**；`no_prune` 全部撞死时间上限。

### 7.3 分支因子实测（b 到底是什么）

`b = --n_select_sample`（README 明说 `number of states to keep from each step (i.e. b in the paper's ToT + BFS algorithm)`）。
**b 不是"并行分支数"**，是**每步保留几个状态**。真正的分支因子是"每个父状态生成几个想法"，实测（b=5 的发布日志，每步 `len(new_ys)/len(ys)`）：

| 步 | 每父状态生成的想法数（均值） |
|---|---|
| step 0 | 9.47 |
| step 1 | 6.36 |
| step 2 | 4.09 |
| step 3 | 4.48 |

⇒ **b=1 时节点数 ≈ 24.4**（1 个父 × 各步分支因子 + step0 的 9.47），**b=5 时 ≈ 84.1**。与 Fig 3(a) 的 (20 → 66.3) 同量级。

---

## 8. 交叉实验（74% / 64% / 31% / 19%）——确切设置

PDF p.13，Table 5 / Table 6：
```
          GSM8K       StrategyQA              GPT-4     GPT-3.5               GPT-4     GPT-3.5
    IO    51          73               IO     7.3%      6%            IO      6.19      4.47
    CoT   86          82               CoT    4.0%      3%            CoT     6.93      5.16
    ToT   90          83               ToT    74%       19%           ToT     7.56      6.62

Table 4: New tasks with             Table 5: Game of 24 with        Table 6: Creative Writing with
zero-shot ToT and GPT-4.            GPT-4 vs GPT-3.5.               GPT-4 vs. GPT-3.5.
```

PDF p.14，Appendix B.2（**唯一给出 64% / 31% 的地方，只有正文，没有表**）：
> `On Game of 24 (we changed 1-shot proposal prompt to 3-shot to make it work), GPT-3.5+ToT's 19% is far worse than GPT-4+ToT's 74%. To further understand the importance of generation vs. evaluation, we ran GPT-4 generation + GPT-3.5 evaluation (64%) and GPT-3.5 generation + GPT-4 evaluation (31%). This suggests the game's bottleneck is thought generation, and different generation/evaluation language models might attain decent results while reducing costs.`

**确切设置（我核到的全部事实）**：
- 任务：**只有 Game of 24**（100 题，index 901–1000，同主实验测试集；Creative Writing 只做了 GPT-3.5 vs GPT-4，未做交叉）。
- 2×2：生成模型 ∈ {GPT-4, GPT-3.5} × 评估模型 ∈ {GPT-4, GPT-3.5}。
- 4 个格子：74%（4gen/4eval）、64%（4gen/3.5eval）、31%（3.5gen/4eval）、19%（3.5gen/3.5eval）。
- ⚠️ **有提示词混淆**：GPT-3.5 生成时把 1-shot proposal prompt 改成 3-shot（"we changed 1-shot proposal prompt to 3-shot to make it work"）⇒ **2×2 不是受控 A/B**（生成格同时变了模型和 shot 数）。
- **重复次数：未报告。置信区间：全文没有。** 全部是 n=100 题的一次性成功率。
- **代码里根本没有跑这个实验的开关**：`src/tot/methods/bfs.py:51` `gpt = partial(gpt, model=args.backend, temperature=args.temperature)` 把**生成和评估绑到同一个全局 `gpt`**，`run.py:45` 也只有 `--backend` 一个后端参数。⇒ 交叉实验需要自己拆全局。

### 8.1 我算的统计功效（n=100，双比例 z 检验）

| 对比 | 差值 | z | p | 判定 |
|---|---|---|---|---|
| 74% vs 64% | 10pp | 1.53 | **0.126** | **不可区分** |
| 74% vs 31% | 43pp | 6.09 | 1.1e-9 | 可区分 |
| 64% vs 31% | 33pp | 4.67 | 3.0e-6 | 可区分 |
| 74% vs 49%(CoT best-of-100) | 25pp | 3.63 | 2.8e-4 | 可区分 |
| 45%(ToT b=1) vs 33%(IO best-of-100) | 12pp | 1.74 | 0.082 | **不可区分** |

各格 95% CI（二项，n=100）：74% → [65.4, 82.6]；64% → [54.6, 73.4]；31% → [21.9, 40.1]；19% → [11.3, 26.7]；45% → [35.2, 54.8]。
MDE（双侧 α=0.05，power=0.8，p̄=0.69）：要检出 **10pp 需要每格 n≈336**；15pp → n≈149；20pp → n≈84。
⇒ **论文的 n=100 只能可靠检出 ≥18–20pp 的差；"74 vs 64" 这 10pp 差在论文的样本量下没有统计意义。**

---

## 9. 论文正文（PDF p.6–7）里"值得抄的判断"，逐字

> `While such an automatic metric might be noisy, Figure 5(b) confirms the finding by showing that humans prefer ToT over CoT in 41 out of 100 passage pairs, while only prefer CoT over ToT in 21 (other 38 pairs are found "similarly coherent").`（PDF p.6）

> `For the former, we sample 5 scores and average them for each task output, and we find these 5 scores usually consistent, with a standard deviation of around 0.56 on average across outputs.`（PDF p.6）

> `Such valuations do not need to be perfect, and only need to be approximately helpful for decision making.`（PDF p.4，`main.tex:165`）

> `the thought (in CoT) or all b thoughts (in ToT) are invalid or impossible to reach 24. Notably, around 60% of CoT samples already failed the task after generating the first step, or equivalently, the first three words (e.g. "4+9"). This highlights the issues with direct left-to-right decoding.`（PDF p.6）

---

## 10. 未取到 / 存疑的东西（如实声明）

1. **DFS 用的 `v_th` 数值**：论文只给符号，代码里**不存在** ⇒ **无法给出具体阈值**（只能自己设计，见 spec §4）。
2. **Fig 3(a) 中 ToT b=2/3/4 的成功率**：论文正文**只报 45% 和 74%**（b=1、b=5）；中间三点 57.1% / 64.6% / 69.5% 是**我从矢量图解出来的**，非论文正文数字，引用时必须标"自 Fig 3(a) 矢量数据反算"。
3. **Fig 3(b) 误差分析的具体百分比**：图内文字未逐条抄录；正文的 "around 60%" 已引。
4. **GPT-3.5 交叉实验的 64% / 31%**：只在 PDF p.14 正文，无表、无重复数、无 CI。发布仓库**没有**对应日志。
5. **Creative Writing 的人工盲评 41/21/38**：只有正文一句，无逐题记录、无评审人数、无一致性检验。
6. **论文 v1 与 v2 的差异**（作者名单已变；正文数字未逐一比对）——本任务用的是 v2。

---

## 11. 抓取配方（复现用）

```bash
# 元数据
curl -sL "https://export.arxiv.org/api/query?id_list=2305.10601" -o arxiv_meta.xml
# 正文（数学会被剥离，只能读文字）
curl -sL "https://arxiv.org/html/2305.10601v2" -o p_html.html
# 正文（保留 MathML alttext，可拿到公式里的数字）—— 本次所有 % / k 数字的来源
curl -sL "https://ar5iv.labs.arxiv.org/html/2305.10601" -o p_ar5iv.html
# PDF（页码定位）
curl -sL "https://arxiv.org/pdf/2305.10601v2" -o p.pdf && pdftotext -layout p.pdf p_pdf.txt
# 源码包（拿图矢量数据）
curl -sL "https://arxiv.org/e-print/2305.10601v2" -o src.tar && tar -xzf src.tar -C srcdir
# 仓库
git clone --depth 1 https://github.com/princeton-nlp/tree-of-thought-llm.git repo
```
HTML → 纯文本且保留公式的提取脚本（本次实际使用）：
```python
raw = open('p_ar5iv.html', encoding='utf-8').read()
def mrepl(m):
    tag = m.group(0)
    a = re.search(r'alttext="(.*?)"', tag, re.S)
    return ' $'+html.unescape(a.group(1))+'$ ' if a else ' [MATH] '
raw2 = re.sub(r'(?s)<math\b.*?</math>', mrepl, raw)
raw2 = re.sub(r'(?i)</(p|div|li|tr|h1|h2|h3|h4|h5|table|figure|figcaption|section|td|th)>', '\n', raw2)
txt = html.unescape(re.sub(r'(?s)<[^>]+>', '', raw2))
```
矢量数据提取（Fig 3(a)）：
```bash
qpdf --qdf --object-streams=disable figures/game24_scale.pdf flat.pdf
# 再用 zlib 解 stream，解析 "x y m" / "x y l" 路径算子
```
