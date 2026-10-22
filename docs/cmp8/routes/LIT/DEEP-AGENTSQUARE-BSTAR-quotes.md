# 逐字摘录：AgentSquare + B* Expansion

> 采集时间：2026-10-22（UTC）· 全部来自一手源：arXiv API / arXiv HTML / GitHub raw / GitHub contents API / Crossref API
> 所有代码片段标注 `仓库路径:行号`（行号对应 raw.githubusercontent 上的原文件）。
> 凡本文档写"未取到 / 未读到"的，即为**实际未取到**，不做摘要脑补。

---

## 0. 身份核对（先做这一步——任务书给的仓库地址是错的）

### 0.1 AgentSquare 论文（arXiv API 一手返回）

```
TITLE: AgentSquare: Automatic LLM Agent Search in Modular Design Space
AUTHORS: ['Yu Shang', 'Yu Li', 'Keyu Zhao', 'Likai Ma', 'Jiahe Liu', 'Fengli Xu', 'Yong Li']
PUBLISHED: 2024-10-08T15:52:42Z
UPDATED (v3): 2025-02-27T13:33:55Z
id: http://arxiv.org/abs/2410.06153v3
COMMENT: 25 pages
CATS: cs.CL
JOURNAL_REF: （空）
DOI: （空）
```

### 0.2 ⚠️ 仓库地址纠正

任务书写的是 `Xtra-Computing/AgentSquare`。**该仓库不存在**：

```
GET https://api.github.com/repos/Xtra-Computing/AgentSquare
  → {"message": "Not Found", "documentation_url": "...", "status": "404"}
  → git/trees/main → Not Found；git/trees/master → Not Found
```

GitHub 搜索 `AgentSquare`（13 个结果），官方实现是：

```
tsinghua-fib-lab/AgentSquare | main | 234 stars
  "The official implementation of the paper \"AgentSquare: Automatic LLM Agent Search in Modular Design Space\""
```

另有 `tsinghua-fib-lab/AgentSquare_website`（官网）、`Cbphcr/Reproduce-of-AgentSquare`（复现）、`ICLR-10021/AgentSquare`（fork，名称暗示曾投 ICLR 2025，**但我没验证是否录用**）。

⇒ **下面所有代码都来自 `tsinghua-fib-lab/AgentSquare`，分支 `main`。**

### 0.3 B* Expansion 论文（Crossref API 一手返回）

```
TITLE: Thinking Is Not Enough: The B* Expansion Technique for Enhancing Autonomous LLM Agents
AUTHORS: ['Sebastián Andrés Mayorquín Posadas', 'Julio Vega']
CONTAINER: Expert Systems
VOLUME/ISSUE/ARTICLE: 43 8 e70333
PUBLISHED: 2026-06-18
TYPE: journal-article
DOI: 10.1111/exsy.70333
```

仓库：`SamthinkGit/Bstar-Expansion`，默认分支 **`master`**（`main` 404）。
⚠️ `README.md` 在仓库里是 **0 字节**（`ls -la` 实测 `0 README.md`）——没有说明文档。

### 0.4 ⚠️ 关键定性：B* Expansion **不是 LLM Agent 架构搜索论文**

它的实验环境是 **Conway's Game of Life**（200×200 棋盘，≤50 个初始活细胞，模拟 300 代，目标＝终局活细胞数最大）。
"Agent" 是一个 LangChain `create_react_agent`，"动作" 是 Python 函数。
**"B\* = B ∪ A\*" 里的 B 是"基础动作基"，A\* 是"LLM 新写出来的复合动作"** —— 不是一个模块池。

---

## 1. AgentSquare —— 模块池数据结构

### 1.1 agent 配置 = 4 槽位 TypedDict

`tsinghua-fib-lab/AgentSquare/search/agent_search.py:17-32`

```python
# Type definitions
class ModuleInfo(TypedDict):
    thought: str
    name: str
    module_type: str
    code: str
    performance: float

class Agent(TypedDict):
    planning: str
    reasoning: str
    tooluse: str
    memory: str

class TestedCase(Agent):
    performance: float
```

### 1.2 模块池 = 4 个 JSON 文件，每条 entry 5 个键

`tsinghua-fib-lab/AgentSquare/search/{planning,reasoning,tooluse,memory}_modules.json`

实测（本地解析，非目测）：

| 文件 | 条目数 | name 列表 |
|---|---|---|
| `planning_modules.json` | 6 | `None, IO, DEPS, HUGGINGGPT, OPENAGI, Voyager` |
| `reasoning_modules.json` | 7 | `IO, COT, COTSC, TOT, SelfRefine, DILU, StepBack` |
| `tooluse_modules.json` | 5 | `None, IO, ANYTOOL, TOOLBENCH, TOOLFORMER` |
| `memory_modules.json` | 5 | `None, DILU, Generative, TP, Voyager` |

entry 键序实测 = `['thought', 'name', 'module type', 'code', 'performance']`。

一条真实 entry（`planning_modules.json` 的 `IO`）：

```json
{
  "thought": "Input the task description to a LLM and directly output the sub-tasks",
  "name": "IO",
  "module type": "planning",
  "code": "class PlanningIO(PlanningBase):\n    def create_prompt(self, task_type, task_description, feedback, few_shot):\n ...",
  "performance": 0.6
}
```

⚠️ 注意 `"module type"`（**带空格**）vs TypedDict 里的 `module_type`（下划线）——`search/agent_search.py:60` 用 `# Manual mapping` 手工对齐。

### 1.3 统一 IO 契约（4 个基类的精确签名）

`tsinghua-fib-lab/AgentSquare/modules/README.md:11-96`（逐字）

```python
class ReasoningBase:
    def __init__(self, profile_type_prompt: str, llms_type: list[str]):
        # profile_type_prompt: the role-playing prompt of large language model
        # llms_type: list of language model types, using first one

class ReasoningCOT(ReasoningBase):
    def __call__(self, task_description: str, feedback: str = ''):
        # task_description: the description of the task to be processed
        # feedback: feedback text to refine the task reasoning
        return reasoning_result
        # reasoning_result: the reasoning result of the current step
```

```python
class MemoryDILU(MemoryBase):
    def __init__(self, llms_type: list[str]):
        # llms_type: list of language model types, using first one

    def __call__(self, current_situation: str = ''):
        # current_situation: the current situation of the task, including the trajectory of tasks to be completed or tasks already completed.
        return updated memory/retrived memory
        # updated memory: the updated memory after adding the current situation
        # retrived memory: the retrived memory of the current situation
```

```python
class PlanningBase():
    def __init__(self, llms_type: list[str]):
        # llms_type: list of language model types, using first one
    
    def __call__(self, task_type: str, task_description: str, feedback: str):
        # task_type: the type of the task
        # task_description: the detailed description of the task
        # feedback: feedback text to refine the task decomposition
        return plan
        # plan: a list of dictionaries, where each dictionary contains a sub-task description, reasoning instruction, and tool-use instruction.
```

```python
class ToolUseBase():
    def __init__(self, llms_type: list[str]):
        # llms_type: list of language model types, using first one

class ToolUseIO(ToolUseBase):
    def __call__(self, task_description: str, tool_instruction: str, feedback_of_previous_tools: str):
        # task_description: the detailed description of the task
        # tool_instruction: find the appropriate tool based on the tool instruction.
        # feedback_of_previous_tools: feedback text to refine the tool selection
        return tooluse_result
        # tooluse_result: the result of the tooluse module
```

### 1.4 模块 `code` 字段的真实内容（逐字，`reasoning_modules.json` 的 `IO`）

```python
class ReasoningIO(ReasoningBase):
    def __call__(self, task_description: str, feedback :str= ''):
        examples, task_description = self.process_task_description(task_description)
        prompt = '''Interact with a household to solve a task. Your instructions must follow the examples.
Here are some examples.
{examples}{memory}
Here is the task:
{task_description}'''
        prompt = prompt.format(task_description=task_description, examples=examples, memory=self.memory_cache)
        reasoning_result = llm_response(prompt=prompt, model=self.llm_type, temperature=0.1, stop_strs=['
'])
        
        return reasoning_result
```

`memory_modules.json` 的 `DILU`（`code` 字段）：

```python
class MemoryDILU(MemoryBase):
    def __init__(self, llms_type, agent_id) -> None:
        super().__init__(llms_type, 'dilu', agent_id)

    def retriveMemory(self, query_scenario):
        # Extract task name from query scenario
        task_name = re.findall(r'Your task is to:\s*(.*?)\s*>', query_scenario)[2]        
        
        # Return empty string if memory is empty
        if self.scenario_memory._collection.count() == 0:
            return ''
            
        # Find most similar memory
        similarity_results = self.scenario_memory.similarity_search_with_score(
            task_name, k=1)
            
        # Extract task trajectories from results
        task_trajectories = [
            result[0].metadata['task_trajectory'] for result in similarity_results
        ]
        
        # Join trajectories with newlines and return
        return '
'.join(task_trajectories)

    def addMemory(self, current_situation):
        # Extract task description
        task_name = re.search(r'Your task is to:\s*(.*?)\s*>', current_situation).group(1)
        
        # Create document with metadata
        memory_doc = Document(
            page_content=task_name,
            metadata={
                "task_name": task_name,
                "task_trajectory": current_situation
            }
        )
        
        # Add to memory store
        self.scenario_memory.add_documents([memory_doc])
```

---

## 2. AgentSquare —— 进化算子

### 2.1 ★ 重组算子（`search/recombination.py`，全文 53 行，逐字）

```python
from utils import llm_response

def recombination(task_description: str, 
                 current_agent: dict[str, str],
                 planning_candidate: dict[str, str],
                 reasoning_candidate: dict[str, str], 
                 tooluse_candidate: dict[str, str],
                 memory_candidate: dict[str, str],
                 tested_case: list[dict[str, float]]) -> list[tuple[str, str, str, str]]:
    prompt = 'You are an AI agent expert. Now you are required to design a LLM-based agent to solve the task of ' \
    + task_description + 'The agent is composed of four fundamental modules(including None): planning, reasoning, tool use and memory. \
    For each module you are required to choose one from the follwing provided candidates. \
    Planning module candidates and descriptions: ' + str(planning_candidate) + ' Reasoning module candidates and descriptions: ' + str(reasoning_candidate) + ' Tool use module candidates and descriptions: ' + str(tooluse_candidate) + ' Memory module candidates and descriptions: ' + str(memory_candidate) \
    + 'The performance of some existing module combinations: ' + str(tested_case) +'. ' \
    + 'You are expected to give a new module combination to improve the performance on the task by considering (1) the matching degree between the module description and task description (2) performance of existing module combinations on the task. \
    Your answer must follow the format and not contain any other information.:' +str({'planning': '<your choice>', 'reasoning': '<your choice>', 'tooluse': '<your choice>', 'memory': '<your choice>'})
    
    model = 'gpt-4o-mini'
    response = llm_response(prompt=prompt, model=model, temperature=0.1)
    agent = eval(response)

    planning = agent['planning']
    reasoning = agent['reasoning']
    tooluse = agent['tooluse'] 
    memory = agent['memory']

    # Create 4 new agents, each replacing one module
    agent1 = {
        'planning': planning,
        'reasoning': current_agent['reasoning'],
        'tooluse': current_agent['tooluse'],
        'memory': current_agent['memory']
    }
    agent2 = {
        'planning': current_agent['planning'],
        'reasoning': reasoning,
        'tooluse': current_agent['tooluse'],
        'memory': current_agent['memory']
    }
    agent3 = {
        'planning': current_agent['planning'],
        'reasoning': current_agent['reasoning'],
        'tooluse': tooluse,
        'memory': current_agent['memory']
    }
    agent4 = {
        'planning': current_agent['planning'],
        'reasoning': current_agent['reasoning'],
        'tooluse': current_agent['tooluse'],
        'memory': memory
    }

    return [agent1, agent2, agent3, agent4]
```

**逐字观察（这几条决定了能不能抄）：**
- `response = llm_response(...)` 之后是 **`agent = eval(response)`**（第 20 行）——用 `eval` 解析 LLM 输出，无 schema 校验、无 try/except。
- 算子输出是 **4 个子代**，每个子代 = 保持 incumbent 的 3 个槽位 + 只替换 **1 个**槽位（`agent1..agent4`）。
- LLM 提的是**一个完整配置**，但真正落到搜索空间里的**只有 4 个单点变异体**。
- 提示词里喂进去的 `tested_case` 是**全量历史实测分**（`agent_search.py` 传 `tested_cases` 全表）。

### 2.2 ★ 进化算子（`search/module_evolution.py`，关键段逐字）

`search/module_evolution.py:36-40`（签名）：

```python
def evolution(current_agent: dict[str, str], 
             planning_archive: list[dict[str, str]], 
             reasoning_archive: list[dict[str, str]], 
             tooluse_archive: list[dict[str, str]], 
             memory_archive: list[dict[str, str]]) -> tuple[list[tuple[str, str, str, str]], dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
```

`search/module_evolution.py:13-34`（LLM 调用）：

```python
@backoff.on_exception(backoff.expo, Exception, max_tries=10)
def get_json_response_from_gpt_reflect(
        msg_list: list[dict[str, str]],
        model: str = 'gpt-4o-mini',
        temperature: float = 0.8
) -> dict:

    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    
    response = client.chat.completions.create(
        model=model,
        messages=msg_list,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    
    content = response.choices[0].message.content
    json_dict = json.loads(content)
    assert json_dict is not None
    return json_dict
```

`search/module_evolution.py:127-143`（必需键 + 重试）：

```python
        required_keys = ["name", "thought", "module type", "code"]

        next_solution_reasoning = get_json_response_from_gpt_reflect(msg_list_reasoning)
        while not ensure_keys_exist(next_solution_reasoning, required_keys):
            next_solution_reasoning = get_json_response_from_gpt_reflect(msg_list_reasoning)

        next_solution_planning = get_json_response_from_gpt_reflect(msg_list_planning)
        while not ensure_keys_exist(next_solution_planning, required_keys):
            next_solution_planning = get_json_response_from_gpt_reflect(msg_list_planning)

        next_solution_memory = get_json_response_from_gpt_reflect(msg_list_memory)
        while not ensure_keys_exist(next_solution_memory, required_keys):
            next_solution_memory = get_json_response_from_gpt_reflect(msg_list_memory)

        next_solution_tooluse = get_json_response_from_gpt_reflect(msg_list_tooluse)
        while not ensure_keys_exist(next_solution_tooluse, required_keys):
            next_solution_tooluse = get_json_response_from_gpt_reflect(msg_list_tooluse)
```

`search/module_evolution.py:166-192`（子代构造，**和 recombination 完全同构**）：

```python
        # Create 4 new agents, each replacing one module
        agent1 = {
            'planning': next_solution_planning["name"],
            'reasoning': current_agent['reasoning'],
            'tooluse': current_agent['tooluse'],
            'memory': current_agent['memory']
        }
        agent2 = {
            'planning': current_agent['planning'], 
            'reasoning': next_solution_reasoning["name"],
            'tooluse': current_agent['tooluse'],
            'memory': current_agent['memory']
        }
        agent3 = {
            'planning': current_agent['planning'],
            'reasoning': current_agent['reasoning'],
            'tooluse': next_solution_tooluse["name"],
            'memory': current_agent['memory']
        }
        agent4 = {
            'planning': current_agent['planning'],
            'reasoning': current_agent['reasoning'], 
            'tooluse': current_agent['tooluse'],
            'memory': next_solution_memory["name"]
        }
        
        evolution_agents.extend([agent1, agent2, agent3, agent4])
```

### 2.3 ★ 进化提示词原文（`module_evolution/prompt_reasoning.py:415-499`）

```python
system_prompt = """You are a helpful assistant. Make sure to return in a WELL-FORMED JSON object."""
```

```python
base = """# Overview
You are an expert machine learning researcher testing various LLM agents. Your objective is to design reasoning modules such as prompts and control flows within these agents to solve complex tasks. The agents have four modules including planning (decomposing a large task into sub-tasks), reasoning (addressing a sub-task), tool use (selecting appropriate external tools for task solving) and memory (read and write experience, observations). \
Your aim is to design an agent with optimal reasoning module performing well on ALFworld (sequential decision making tasks with steps including finding hidden objects, moving objects and manipulating objects with other objects ).

# Task Overview:
ALFworld is a suite of text-based environments that challenge an agent to solve multi-step tasks in a variety of interactive environments. It includes 6 types of tasks in which an agent needs to achieve a high-level goal (e.g. examine paper under desklamp) by navigating and interacting with a simulated household via text actions (e.g. go to coffeetable 1, take paper 2, use desklamp 1).
To solve this task, you need to first decompose the task using the planning module. Reasoning and memory modules are then used to solve each subtask. This requires strong command following, as well as common sense reasoning.
...
# Reasoning Module Template:
```python
class REASONING():
    def __init__(self, profile_type_prompt, memory, tooluse, llms_type):
        # Class initialization, do not modify this part
        self.feedback = ''
        self.profile_type_prompt = profile_type_prompt
        self.memory = memory
        self.llm_type = llms_type[0]
        self.tooluse = tooluse
        self.task_name_cache = None
    def __call__(self, task_description: str, tool_instruction :str='', feedback :str=''):
        # Call tools use modules and memory modules, do not modify this part
        task_name = re.findall(r'Your task is to:\s*(.*?)\s*>', task_description)
        if self.memory is not None:
            if self.task_name_cache is not None and self.task_name_cache == task_name:
                pass
            else:
                self.task_name_cache = task_name
                self.memory_cache = self.memory(task_description)
        else:
            self.memory_cache = ''
        if self.tooluse is not None:
            tooluse = self.tooluse(task_description, tool_instruction)
        else:
            tooluse = ''
        # Split into two parts, on is the task soleution track example, the other is the current task
        split_text = task_description.rsplit('You are in the', 1)
        # task solution track examples
        examples = split_text[0]
        # currect task
        task_description = 'You are in the' + split_text[1]
        '''
        Fill in your code here.
        '''
        return reasoning_result
...
```

```python
# Discovered architecture archive
Here is the archive of the discovered reasoning module architectures:

[ARCHIVE]

The performance represents the completion rate of the task. 

# Output Instruction and Example:
The first key should be ("thought"), and it should capture your thought process for designing the next function. In the "thought" section, first reason about what should be the next interesting agent to try, then describe your reasoning and the overall concept behind the agent design, and finally detail the implementation steps.
The second key ("name") corresponds to the name of your next agent architecture. 
Finally, the last key ("code") corresponds to the exact module function in Python code that you would like to try. You must write a COMPLETE CODE in "code": Your code will be part of the entire project, so please implement complete, reliable, reusable code snippets.

Here is an example of the output format for the next agent architecture:

[Reasoning_example]

You must strictly follow the exact input/output interface used above. Also, it could be helpful to set the LLM’s role and temperature to further control the LLM’s response. DON'T try to use some function that doesn't exist. In __call__(), you need to specify the instruction, input information, and the required output fields for various LLM agents to do their specific part of the architecture. 

# Your task
You are deeply familiar with prompting techniques and the agent works from the literature. Your goal is to maximize the specified performance metrics on the given task by proposing interestingly new reasoning module including prompts and control flows.
Observe the discovered agents carefully and think about what insights, lessons, or stepping stones can be learned from them.
Be creative when thinking about the next interesting agent to try. You are encouraged to draw inspiration from related agent papers or academic papers from other research areas.
Use the knowledge from the archive and inspiration from academic literature to propose the next interesting agentic system design.
For the directly callable function methods mentioned in the inference module example, you can call them directly and do not need to define them. If you need to create new function methods, you need to make sure that the function is complete and runnable.
You need to learn as much as possible from well-performed reasoning modules.
THINK OUTSIDE THE BOX.

"""
```

### 2.4 进化算子的 archive 注入（`module_evolution/prompt_reasoning.py:500-510`）

```python
def get_prompt_reasoning(current_archive):
    archive_str = ",\n".join([json.dumps(sol) for sol in current_archive])
    archive_str = f"[{archive_str}]"
    prompt = base.replace("[ARCHIVE]", archive_str)
    prompt = prompt .replace("[Reasoning_example]", json.dumps(Reasoning_example))

    return system_prompt, prompt

def get_init_archive_reasoning():
    return [reasoning_IO, reasoning_CoT, reasoning_CoT_SC, reasoning_ToT, reasoning_self_refine, reasoning_Dilu, reasoning_Stepback]
```

---

## 3. AgentSquare —— 代理性能预测器（`search/module_predictor.py`）

### 3.1 训练集构造（`search/module_predictor.py:128-159`）

```python
def predict_performance(candidates: Dict[str, Dict[str, str]], archives: Dict[str, List[ModuleInfo]], agents: List[dict[str, str]]):
    # Read alfworld_results.json file
    with open('alfworld_results.json', 'r') as f:
        alfworld_results = json.load(f)

    # Iterate through results to generate golden_case
    golden_case = []
    golden_case_list = []
    for result in alfworld_results:
        if result['performance'] == {}:
            continue
        case = {
            'planning': result['config']['planning'],
            'reasoning': result['config']['reasoning'], 
            'tooluse': result['config']['tooluse'],
            'memory': result['config']['memory'],
            'performance': result['performance']
        }
        golden_case.append(get_module_code(case))
        golden_case_list.append(case)
        
    # Randomly split into training and test sets
    import random
    random.seed(42)
    combined = list(zip(golden_case, golden_case_list))
    random.shuffle(combined)
    golden_case[:], golden_case_list[:] = zip(*combined)
    train_split = int(len(golden_case) * 0.8)
    train_data = golden_case[:train_split][:85]
    for item in train_data:
        item['performance'] = item.pop('label')
```

**逐字观察：**
- **没有训练任何模型**。这是 **zero-shot in-context 回归**。
- 训练样本 = 已实测的 (配置, 分数) 对，**每个样本的内容是 4 个模块类的完整源码**（`get_module_code` 用 `inspect.getsource`）。
- `random.seed(42)` + shuffle + 80% + **截断到 85 条**。
- 标签从 `'label'` 键搬到 `'performance'` 键（`get_module_code` 产出 `{"prompt_answer": ..., "label": ...}`）。

### 3.2 推理提示词（`search/module_predictor.py:185-189`）

```python
    prompt = f"""You are a performance estimator. Now you need to estimate the performance of a LLM-based agent solving an ALFworld task (sequential decision making tasks with steps including finding hidden objects, moving objects and manipulating objects with other objects ). The agent is composed of four fundamental modules: planning, reasoning, tool use and memory. Planning module candidates and descriptions: {candidates['planning']}, Reasoning module candidates and descriptions: {candidates['reasoning']}, Tool use module candidates and descriptions: {candidates['tooluse']}, Memory module candidates and descriptions: {candidates['memory']}. The performance of some existing module combinations: {train_data}. The module combination you need to predict: {batch}. You're going to have to predict each of the {len(batch)} combinations I've given you. Be sure to give exact predictions. Your output should be of the following json format:
    {{'predictions':[{{'planning':'deps', 'reasoning':'io', 'tooluse':'None', 'memory':'dilu', 'performance': ''}},
    {{'planning':'openagi', 'reasoning':'CoT', 'tooluse':'None', 'memory':'generative', 'performance': ''}}]}}"""

    response = llm_response(prompt=prompt, model='gpt-4o', temperature=0.0)
```

### 3.3 输出解析（`search/module_predictor.py:190-204`）

```python
    print(response)
    result = eval(response)['predictions']
    # Check if the result length matches the batch length, fill with 0 if not matching
    if len(result) < len(batch):
        print(f"Warning: Number of prediction results ({len(result)}) is less than batch size ({len(batch)}), will be filled with 0")
        # Fill in missing prediction results
        while len(result) < len(batch):
            result.append({
                'planning': 'None',
                'reasoning': 'None', 
                'tooluse': 'None',
                'memory': 'None',
                'performance': 0.0
            })
    return [pred['performance'] for pred in result]
```

### 3.4 节省成本的机制在哪

**不在预测器里，在主循环里**（`search/agent_search.py:468-488`）：

```python
            # 5. Predict performance of recombined agents
            print("[Predicting Recombined Agent Performance]")
            predicted_scores = predict_performance(candidates, archives, filtered_recombination_agents)
            
            # Find agent with highest predicted score
            best_agent_idx = predicted_scores.index(max(predicted_scores))
            top_agent = filtered_recombination_agents[best_agent_idx]
            
            # 6. Test the best predicted agent
            print("[Testing Best Recombined Agent]")
            print(f"Predicted agent performance: {max(predicted_scores)}, configuration: {top_agent}")
            performance = test_agent(top_agent, archives)
            update_tested_cases(tested_cases, top_agent, performance)
            iteration_test_count += 1
            print(f"Actual agent performance: {performance}")
```

⇒ **4 个重组子代只预测，只有 argmax 的那 1 个做真机评测**（`test_agent` → `run_benchmark(..., 50)`，50 个 episode）。

---

## 4. AgentSquare —— 目标函数（论文逐字）

### 4.1 §3.1 问题形式化

> In the proposed modular design space, an LLM agent A can be instantiated with the combination of a planning module P , a reasoning module R , a tooluse module T and a memory module M , denoted as A=(P,R,T,M) .
> Given the task description d and the set of all possible modules with standardized IO interface {P,R,T,M} .
> We formulate an optimization problem for searching LLM agent architectures within the modular design space.
> **The objective is to identify the optimal module combination in a solution space defined by a Cartesian product of four design dimensions to maximize agent performance.**
> Let the performance evaluation function of the task be Eval_d(·) , where the specific metric varies in different tasks as discussed in Appendix A.1 . The optimization problem of MoLAS is defined as follows:
>  argmax_{P∈P,R∈R,T∈T,M∈M} Eval_d(P,R,T,M).  (1)

### 4.2 任务指标口径（Appendix A.1）

> Specifically, the evaluation metric is "success rate" for ALFWorld and M3ToolEval, "task score (defined as the average reward obtained across episodes)" for Webshop, "progress rate" for SciWorld and PDDL, and "micro pass rate" for TravelPlanner.

### 4.3 ⚠️ 全文关键词命中（本地对 arXiv HTML 抽取文本做正则统计）

| 关键词 | 命中次数 | 说明 |
|---|:-:|---|
| `novelty` | **0** | 全文没有 |
| `entropy` | **0** | 全文没有 |
| `fitness` | **0** | 全文没有 |
| `regret` | **0** | 全文没有 |
| `diversit` | 1 | **只在参考文献里**（Nasir et al. 2024, LLMATIC, GECCO），正文无 |
| `coverage` | 1 | 散文里一句 "broadens the coverage of child samples"，**不是目标项** |
| `objective` | 1 | 即 4.1 那句 argmax |
| `maximiz` | 1 | 同上 |

⇒ **AgentSquare 的目标函数是纯任务标量。全文没有任何非任务标量目标（无多样性、无新颖度、无熵、无覆盖度）。**

### 4.4 消融表（Table 2，GPT-4o）

```
Method                     Webshop  ALFWorld  SciWorld  M3Tool  TravelPlanner  PDDL
AgentSquare (full)           0.607     0.695     0.781    0.524       0.583    0.669
w/o module evolution          0.564     0.649     0.736    0.502       0.577    0.614
w/o module recombination      0.560     0.616     0.710    0.481       0.280    0.669
```

Table A.5（GPT-3.5）：
```
AgentSquare (full)           0.617     0.651     0.432    0.285       0.520    0.219
w/o module evolution          0.595     0.623     0.288    0.236       0.483    0.202
w/o module recombination      0.578     0.546     0.310    0.258       0.267    0.173
```

### 4.5 停止条件与预算

> The initial agent is set as a random module combination, and **the search process terminates after 5 consecutive iterations without performance improvement.**

Algorithm 1 的输入（论文原表）：
> Input: Initial agent A_0 , targeted task descriptions d , **maximum evolution episode K** , **population size N per evolution phase** , standardized module pools {P,R,T,M} , experience pool E

Table A.6：
```
                 Webshop  ALFWorld  SciWorld  M3Tool  Travel  PDDL
Avg cost (GPT-3.5)  $3.16    $4.25     $1.92    $2.43    $1.84  $2.70
Iterations (GPT-3.5)   23       21        8       14        9     17
Avg cost (GPT-4o)   $10.51   $13.96    $42.14   $26.03   $29.75  $26.94
Iterations (GPT-4o)    18       15        9       18        8     12
```

### 4.6 预测器成本（§4.3 逐字）

> For instance, the evaluation cost of the predictor is only about **0.025%** of the cost of a full evaluation based on GPT-4o in ALFWorld, demonstrating its remarkable cost-efficiency.

### 4.7 ⚠️ 仓库级不一致（会挡路，必须知道）

`search/module_evolution.py:97` 调用：
```python
    system_prompt, prompt = get_prompt_reasoning(reasoning_modules, reasoning_last_feedback)
```
**2 个参数。** 而仓库里唯一存在的 `module_evolution/prompt_reasoning.py:500` 定义是：
```python
def get_prompt_reasoning(current_archive):
```
**1 个参数。** 4 个 `prompt_*.py` 全是这个情况（`prompt_planning.py:388`、`prompt_memory.py:345`、`prompt_tooluse.py:268` 均为 1 参）。

⇒ **`search/` 那条管线按现状跑不起来（TypeError）**，除非把 4 个 `prompt_*.py` 换成 2 参版本。
而且 2 参版本要读 archive 条目里的 `'feedback'` 键，但仓库里 `*_modules.json` 的 5 个键里**没有 `feedback`**。

⇒ **"照这个范式做消融"时不能直接抄 `search/`，只能抄它的算子形状。**

### 4.8 ⚠️ 消融在代码里没有开关

`search/agent_search.py` 全文**没有任何 `--ablation` / `if ablation` 分支**（我通读了 535 行）。
`w/o module evolution` 的**唯一可能实现** = 跳过主循环第 1–3 步（`# 1. Module evolution phase` / `# 2. Test new modules` / `# 3. Test agents generated by evolution`），只跑第 4–6 步（recombination + predictor + 测 top-1）。
`w/o module recombination` 反之。
⇒ **消融范式是"拿掉一整个阶段"，不是"拿掉一个算子内部的某条分支"。** 这一点对我们自己做消融有直接约束：我们的消融粒度只能是"关掉某阶段"。

### 4.9 主循环骨架（`search/agent_search.py:385-497`，节选关键行）

```python
        for iteration in range(num_iterations):
            ...
            # 1. Module evolution phase
            evolution_results = evolution(
                current_agent,
                archives['planning'],
                archives['reasoning'],
                archives['tooluse'],
                archives['memory']
            )
            ...
            # 4. Recombination phase
            recombination_agents = recombination(
                TASK_DESCRIPTION,
                current_agent,
                candidates['planning'],
                candidates['reasoning'],
                candidates['tooluse'],
                candidates['memory'],
                tested_cases
            )
```

选择规则（**不是 GA，没有锦标赛，没有适应度比例**）：
```python
            # Update current agent and performance (if there's a better one)
            for agent, performance in evolution_test_results:
                if performance > current_performance:
                    current_agent = agent
                    current_performance = performance
```
⇒ **精英保留（elitism），1 个 incumbent，贪心接受。**

固定超参（代码实测）：
- `num_iterations = 10`（`search/agent_search.py:377`）
- 每次真机评测 `n = 50` 个 episode（`run_benchmark(agent, 50)`）
- 被评测 agent 的 LLM：`llms_type=['gpt-4o-mini']`（`search/agent_search.py:100`）
- 重组提议 LLM：`gpt-4o-mini`, `temperature=0.1`（`search/recombination.py:18-19`）
- 进化 LLM：`gpt-4o-mini`, `temperature=0.8`（`search/module_evolution.py:16-17`）
- 预测器：`gpt-4o`, `temperature=0.0`（`search/module_predictor.py:189`）

---

## 5. B* Expansion —— 全部实现

### 5.1 基础动作基 B（`game_of_life/tools/template.py`，全文 34 行，逐字）

```python
from langchain_core.tools import tool
from game_of_life.core import get_current_game


@tool
def reason(reasoning: str) -> bool:
    """Reason about your plan."""
    return True


@tool
def clear_grid(x: int, y: int) -> bool:
    """Empty the grid of the current game. Consumes 0 cells."""
    game = get_current_game()
    game.clear()
    return True


@tool
def add_cell(x: int, y: int) -> bool:
    """Add a cell at the specified coordinates. Consumes 1 cell."""
    game = get_current_game()
    game.add_cell(x, y)
    return True


@tool
def get_grid() -> str:
    """Look at the current grid. Consumes 0 cells."""
    game = get_current_game()
    int_matrix = game.grid.astype(int)
    lines = ["".join(str(cell) for cell in row) for row in int_matrix]
    grid = "\n".join(lines)
    return grid
```

### 5.2 ★ A\* 生成提示词原文（`game_of_life/agents/agents.py:36-66`，逐字）

```python
GENERATOR_PROMPT = """
You are an AI assistant helping to design new atomic actions ("tools") for
Conway's Game of Life.

The file you are editing contains Python functions. Each function defines a new
action that can be used by a Game of Life agent to place patterns on a {GRID_SIZE}x{GRID_SIZE}
grid. These actions are used at the beginning of each game: the agent can choose
up to {ALIVE_CELLS} CELLS to place before the simulation runs for {NUM_OF_GENERATIONS} generations
using standard Conway rules.

**Goal of the agent:** reach the maximum number of alive cells after {NUM_OF_GENERATIONS} generations.
This cells can be the same as the ones placed at the beginning, or new ones that
were born during the simulation thanks to the original placements.

Each function must follow the structure of the others: do not rewrite
the existing functions, but rather a new one that can be used by the agent to
play better the game. You can use only the functions already defined in the file
to implement your new function.

Your goal: Follow exactly these steps:
1. Write a short reasoning *as Python docstring* explaining the intuition behind
the pattern you're adding — why it may be beneficial in Conway's Game of Life. (All the generation
will be pasted to the file, so be careful not to overwrite or add invalid sintax)

2. Then define a unique new Python function following the same pattern as the others.

The file is the following:
{file_content}

Your response will be pasted at the end of the file.
"""
```

### 5.3 ★ 生成器实现（`game_of_life/agents/agents.py:127-165`，逐字）

```python
class ToolsGeneratorAgent:
    def __init__(self, life_player: LifePlayer, model: str = "gpt-4.1-mini"):
        self.model = ChatOpenAI(model=model, temperature=0.6)
        self.life_player = life_player

    def generate_tool_once(self):
        with open(self.life_player.tool_env, "r", encoding="utf-8") as f:
            content = f.read()

        prompt = GENERATOR_PROMPT.format(
            GRID_SIZE=GRID_SIZE,
            ALIVE_CELLS=ALIVE_CELLS,
            NUM_OF_GENERATIONS=NUM_OF_GENERATIONS,
            file_content=content,
        )

        with console.status("[bold green]Generating new tool..."):
            response = self.model.invoke(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": "Start now writing the docstring and the new function.",
                    },
                ]
            )
        lines = response.content.split("\n")
        if lines[0].startswith("```"):
            response.content = "\n".join(lines[1:-1])

        panel = Panel(
            response.content,
            title="Tool Generation",
            border_style="bold green",
        )
        pprint(panel)

        with open(self.life_player.tool_env, "a", encoding="utf-8") as f:
            f.write("\n" + response.content + "\n")
```

**逐字观察：**
- 生成器**读整个当前文件**（`file_content`）⇒ 新动作能看到历史动作。
- 只剥 markdown 围栏，**没有任何语法/语义校验**。
- 直接 `append` 到文件尾部 ⇒ **动作空间单调增长，永不删除**。
- `temperature=0.6`。

### 5.4 ★ B\* = B ∪ A\* 的实现：动作空间 = 那个文件里的所有函数

`game_of_life/agents/agents.py:168-185`（逐字）：

```python
def load_functions_from_file(file_path: Path) -> dict:

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    exec_globals = {
        "__builtins__": __builtins__,
        "get_current_game": get_current_game,
    }
    local_ns = {}

    exec(source, exec_globals, local_ns)

    return {
        name: obj
        for name, obj in local_ns.items()
        if callable(obj) and isinstance(obj, StructuredTool)
    }
```

`game_of_life/agents/agents.py:72-91`（每个玩家一份独立动作空间）：

```python
class LifePlayer:

    def __init__(self, model: str = "openai:gpt-4.1-mini", env: Optional[Path] = None):
        self.id = str(uuid.uuid4())
        if env is not None:
            self.tool_env = env
        else:
            self.tool_env = ENV_DIR_PATH / f"tools-{self.id}.py"
            shutil.copy(TEMPLATE_PATH, self.tool_env)
        self.model = model

    def play_once(self, animate: bool = False, interval: int = 5) -> int:
        game = GameOfLife(
            width=GRID_SIZE,
            height=GRID_SIZE,
            max_cells=ALIVE_CELLS,
        )
        set_current_game(game)

        tools = load_functions_from_file(self.tool_env)
```

⇒ **B\* 就是"那个 .py 文件里所有 `@tool` 函数的并集"**。`shutil.copy(TEMPLATE_PATH, self.tool_env)` = 初始 B（4 个工具）。

### 5.5 ★ 扩展循环（`lab/agentic_play_batch.py:48-64`，逐字）

```python
def run_round(round_idx):
    """
    Runs a single game for the global player/tool_gen,
    returns (player.id, round_idx, pjoints).
    """
    with tracing_context(enabled=False):
        done = False
        while not done:
            try:
                pts = player.play_once(animate=False, interval=1)
                tool_gen.generate_tool_once()
                done = True
            except Exception:
                logging.error("Retrying the round...", exc_info=True)
                continue

    return player.id, round_idx, pts
```

⇒ **一轮 = 先用当前 B\* 玩一局拿分 → 再追加一个新动作。**
⇒ 生成器**看不到分数**（`ToolsGeneratorAgent` 没有任何 score/points 入参）⇒ 扩展是**开环**的。

### 5.6 ★ 唯一的保护（`game_of_life/agents/agents.py:113-115`，逐字）

```python
        assert (
            game.points <= ALIVE_CELLS
        ), "LLM exceeded the maximum number of alive cells. Exit"
```

### 5.7 ⚠️ "扩展有用"的判据：**代码里没有**

我在 B* 仓库全部 Python 文件里 grep 了 `accept|reject|valid|filter|equivalen|duplicat|prune|discard`，命中只有 1 处，且是提示词里的一句 "invalid sintax"。

⇒ **发布代码里没有任何"接受/拒绝新动作"的判据**：
- 无结构合法性检查（生成的代码若语法错，`exec` 抛异常 → `run_round` 的 `except Exception` 捕获 → `continue` → **下一轮 `play_once` 再 `exec` 同一个坏文件 → 死循环**）。
- 无冗余/等价去重。
- 无按效用取舍。

**论文声称**（§3.3 逐字，与代码不符）：
> To ensure the validity of the expanded action space, each candidate action proposed for A* undergoes a filtering process before inclusion. First, structurally invalid actions (e.g., malformed arguments or undefined operations) are discarded. Second, redundant actions—defined as actions functionally equivalent to existing elements in B*—are removed using deterministic equivalence checks over action signatures. Only actions passing both criteria are incorporated into A_{n+1}*.
>
> These candidate actions are then validated and either incorporated into A_{n+1}* or discarded based on their utility in improving solution quality or expanding coverage of the action space.

**论文同时强调生成器与性能隔离**（§5.1 逐字）：
> To mitigate potential bias in the construction of A* , the generation of new actions is performed using the same model C but with **strict separation between generation and execution contexts**. Specifically, **the tool-generation process has no access to performance outcomes from the experimental runs** and is executed independently for each run without shared memory or cross-run information. This design avoids direct optimization of A* towards observed test-time performance and ensures that improvements in B* arise from structural action-space expansion rather than closed-loop adaptation to specific trajectories.

⇒ 论文的"过滤"是 **formally stated but not implemented**；且实验设计**故意**不让扩展闭环。

### 5.8 论文 §3.3 的形式化（B\* 与 A\* 的定义，逐字关键句）

> We now introduce a finite subset B ⊂ A , called the **action basis**, which serves as a generative core for the entire space A . The set B is assumed to be **complete**, in the following formal sense: An action basis B ⊂ A is complete if and only if every action a ∈ A can be expressed as a finite composition of actions in B
>
> we define A* , the **action space approximator**, as the set of all actions that can be generated by a growing sequence action spaces A_0*, A_1*, … ⊂ A , where: A_0* = ∅ , A_n* ⊂ A_{n+1}* , ∪_{n=0}^∞ A_n* = A
>
> Finally, we define the expanded action space B* as the union of the action basis B and a growing approximator A* ⊂ A: **B* = B ∪ A***

### 5.9 ★ 论文 Table 1 与仓库 CSV 的**逐条复算**（我本地跑的）

论文 Table 1（§5.2）原文：

```
Model          B* expansion   Median   Total range
gpt-4o-mini    —                50        0–820
gpt-4o-mini    ✓                93       30–1292
o4-mini        —                40        0–1504
o4-mini        ✓               253        0–1870
```

我从 `SamthinkGit/Bstar-Expansion` 仓库 `results/` 拉下 CSV 并本地复算中位数 / 极值：

| 仓库文件 | n | 我算的 median | 我算的 min–max | 论文 Table 1 | 对得上？ |
|---|:-:|---:|---:|---|:-:|
| `results/env_results_r0.csv` | 30 | **50.0** | 0 – 820 | gpt-4o-mini, 无 B\*：50, 0–820 | ✅ |
| `results/env_results_r40.csv` | 30 | **93.5** | 30 – 1292 | gpt-4o-mini, 有 B\*：93, 30–1292 | ✅ |
| `results/reasoning_results.csv` | 30 | **40.0** | 0 – 1504 | o4-mini, 无 B\*：40, 0–1504 | ✅ |
| `results/env_results_r40_reasoning.csv` | 30 | **253.0** | 0 – 1870 | o4-mini, 有 B\*：253, 0–1870 | ✅ |

⇒ **Table 1 四行全部从发布数据复算成功。**（第四行 raw 拉取失败，用 GitHub contents API base64 取到。）

### 5.10 ★ 40 轮扩展曲线的本地复算（`results/results_40_rounds.csv`，20 player × 40 轮 = 800 行）

我本地按轮算中位数（节选）：

```
round  n  median  mean   min  max        round  n  median  mean   min  max
    1 20    50.0  239.8     0 1256           21 20   225.5  342.0    26 1315
    2 20    48.0   40.6     0   76           22 20    98.5  218.8    15 1437
    3 20    48.0  104.8     0 1236           23 20   136.5  319.2    40 1240
    4 20    47.5   40.9     0   50           24 20   210.5  202.6     7  400
    5 20    48.0   85.7    12  351           25 20   129.5  201.4    21 1030
    6 20    48.5  126.2    22 1505           26 20   129.0  206.4    31 1143
    7 20    96.0  115.3    20  421           27 20    92.0  169.8    27 1221
    8 20    83.0  115.4    23  911           28 20   100.5  126.3    37  322
    9 20    92.5  154.7    16 1241           29 20    94.5  152.6    36  904
   10 20    92.5  182.2    33 1018           30 20   117.5  167.9    18  581
   11 20    98.0  178.8    42  977           31 20    95.0  128.3    22  699
   12 20   100.0  129.0    35  437           32 20    98.0  178.4    16 1060
   13 20   128.0  234.1    16 1065           33 20   151.5  180.1    38  713
   14 20    98.5  235.2    38  905           34 20    98.5  179.2    20 1246
   15 20   103.5  199.3    30 1065           35 20    93.0  101.5    20  239
   16 20    89.5  160.7     6 1404           36 20   145.0  218.7    22 1246
   17 20    99.5  180.6    40  983           37 20    98.0  171.8     0 1068
   18 20    97.5  164.2    26  612           38 20   107.5  118.8    19  274
   19 20   127.5  218.2    24  886           39 20    99.5  149.7    17  565
   20 20    98.5  170.8    27  608           40 20    87.5  136.4     7  834
```

**逐字对上论文叙述**：
> during the initial rounds, the agent tends to stabilize around 50 points, which roughly corresponds to the number of alive cells it is allowed to place initially. ... However, **starting around round 7, there is an abrupt increase in performance.** ... The trend stabilizes gradually, **reaching median values close to 100 points (double the initial score) by round 25.**
> When repeating and extending the same experiment to 40 rounds (Figure 4), we observe that the **median performance maintains stable**, indicating that the reach of the LLM has saturated under the current cognitive function.

⇒ 论文的三句话（≈50 平台 → 第 7 轮突增 → 第 25 轮 ≈100 → 40 轮饱和）**全部被发布 CSV 复算证实**。
⚠️ 但注意：均值远高于中位数（如 round 1 均值 239.8 vs 中位数 50；round 6 均值 126.2 vs 中位数 48.5），**分布是重尾的**；用均值会讲一个和论文不同的故事。

### 5.11 B* 的三个实验臂（代码级）

| 脚本 | 角色 | 模型 | 规模 |
|---|---|---|---|
| `lab/agentic_play_batch.py` | **B\* 臂**：边玩边扩 | player & generator 都用 `gpt-4.1-nano` | 20 players × 25 轮 |
| `lab/agentic_play_batch_reasoning.py` | **LRM 对照臂**：只推理不扩展 | `o4-mini` | 4 agents |
| `lab/agentic_play_env_batch.py` | **冻结动作空间评测臂**：给一个 .py 文件跑一局 | `o4-mini` | 10 agents，文件从 `tools_env_40_rounds/` 随机抽 |

（`lab/agentic_play_batch.py:35-36`：`player = LifePlayer(model="openai:gpt-4.1-nano")` / `tool_gen = ToolsGeneratorAgent(player, model="gpt-4.1-nano")`；
`lab/agentic_play_batch_reasoning.py:29`：`player = LifePlayer(model="openai:o4-mini")`；
`lab/agentic_play_env_batch.py:26`：`player = LifePlayer(model="openai:o4-mini", env=env_file)`。）

### 5.12 论文自陈的局限（§7 逐字，节选）

> First, as the expanded action space A* grows, the cognitive load on the language model increases due to the need to select among a larger set of candidate actions. This may introduce a 'paradox of choice' effect, where overly rich action spaces can degrade decision quality if not properly structured or ranked. ... Third, the effectiveness of B* may depend on the structure of the task. In highly sequential or syntax-constrained domains (e.g., program synthesis or formal verification), **naive action expansion may not yield improvements unless the generated actions preserve strict semantic correctness.** Finally, the current evaluation is limited to a single controlled environment (Conway's Game of Life).

---

## 6. Part C：非任务标量目标的已有工作（全部 arXiv API 核过身份）

### 6.1 核验记录

| arXiv id | 标题（API 原样） | 作者 | 首次提交 | 核验方式 |
|---|---|---|---|---|
| `2602.1062`（canonical `2602.01062`） | SetPO: Set-Level Policy Optimization for Diversity-Preserving LLM Reasoning | Li Chenyi, Zhang Yuan, Wang Bo, Ma Guoqing, Tang Wei, Huang Haoyang, Duan Nan | 2026-02-01 | arxiv.org/abs 页 `citation_*` meta |
| `2412.7779`（canonical `2412.07779`） | Evolution of Thought: Diverse and High-Quality Reasoning via Multi-Objective Optimization | Qi Biqing, Qian Zhouyi, Luo Yiang, Gao Junqi, Li Dong, Zhang Kaiyan, Zhou Bowen | 2024-11-24 | 同上 |
| `2609.05992` | MOAE: Multi-Objective Agent Evolution with Pareto-Preserving Search | Hengle Jiang, Qijun Cai, Ziying Luo, Ke Tang | 2026-09-05 | arXiv API |
| `2606.25198` | Heuresis: Search Strategies for Autonomous AI Research Agents Across Quality, Diversity and Novelty | Antoniadis, Nathani, Saha, Amayuelas, Bercovich, Weng, Baskaran, Bhatia, William Yang Wang | 2026-06-23 | arXiv API |
| `2609.10052` | Direct Diversity Optimization for Diverse Successful Trajectories in Preference Post-Training | Junwon Ko, Dong-Jae Lee, Minchan Kwon, Sunghyun Baek, Junmo Kim | — | arXiv API（`ti:` 标题检索） |
| `2605.19461` | Beyond Mode Collapse: Distribution Matching for Diverse Reasoning | （多作者，见正文） | — | arxiv.org/html 链接 + 正文 |
| `2603.24844` | Reaching Beyond the Mode: RL for Distributional Reasoning in Language Models | Isha Puri, Mehul Damani, Idan Shenfeld, Marzyeh Ghassemi, Jacob Andreas, Yoon Kim | — | arXiv API |
| `2607.02807` | SwarmResearch: Orchestrating Coding Agents for Open-Ended Discovery | Yuvraj Virk, Zack Edds, Chunqiu Steven Xia, Lingming Zhang | 2026-07-02 | arXiv API |

⚠️ 前 4 篇的 arXiv id 是**我从二手博客（wispaper.ai / lacuna.tiptreesystems.com / connectedresearchers.top / arxiv-vanity）里挖出来再去一手核的**——那些博客本身不可信，**引用时只引上面这一行的一手元数据**。

### 6.2 EoT（arXiv 2412.7779）的目标函数（逐字）

> EoT formulates reasoning as a **multi-objective optimization (MOO)** problem, balancing both answer quality and diversity.
> Maximize_{A∈A} M(A) = [ M^Q(A), M^N(A) ]^T ,  (1)
> where A = S(f, p_q) is the set of answers returned after the search strategy S is executed. **M^Q(A)** denotes the **quality score** of an answer, with higher values indicating a greater likelihood of correctness; **M^N(A)** represents the **novelty score** of answer A, with a higher score signifying greater distinctiveness compared to other answers.

参考基准化的质量分（逐字）：
> we introduce a **reference-based scoring mechanism**. For each question, we first use the MLLM to generate a reference answer A_ref, and then perform reference-based scoring in subsequent evaluations: **M^Q(A) = f(p_q, p_s, A_ref, A)**, which provides a standard for the scoring process and reduces subjective bias in the MLLM scoring.

支配关系（逐字）：
> for any two candidate answers A_i and A_j, A_i is considered dominated by A_j (A_i ≺ A_j) if and only if both **M_N(A_i) ≤ M_N(A_j)** and **M_Q(A_i) ≤ M_Q(A_j)** hold simultaneously. ... This results in L non-dominated levels, with each level 1≤l≤L containing a set A_l. Within each level, candidates are ranked according to their quality score M_Q(A)

算法（Appendix A 伪码逐字）：
> 3: Initialize candidate set A={A_i}, where each A_i=f(p_q) is generated by the LLM
> 4: Generate a reference answer A_ref using LLM
> 5: Calculate the initial quality scores M^Q(A_i) and novelty scores M^N(A_i) for each A_i∈A
> 6: for each generation t=1,2,…,T do
> 7:   Step 1: Scoring ... Recalculate the novelty score M^N(A_i) for all candidates in A, **including updates due to new candidates**
> 13:  Step 2: Ranking and Selection. Perform non-dominated sorting on the candidates based on their M^Q and M^N scores
> 16:  Step 3: Crossover and Mutation
> 17:    Generate N_C crossover offspring {A_i^C} using selected parent pairs A'_i and A'_j: **A^C = f(p_q, p_C, A'_i, A'_j)**
> 19:    Generate N_M mutation offspring {A_i^M} using randomly selected parent A'_i: **A^M = f(p_q, p_M, A'_i)**
> 21:  Update the candidate set A = A ∪ {A_i^C} ∪ {A_i^M}
> 22:  Expand the candidate set size: N×=2

多样性指标的落地方式（逐字，从摘要/贡献段）：
> Using MLLMs to score generated answers and construct a quality metric, while **defining a novelty metric based on semantic similarity**, forming an MOO problem that balances quality and diversity
> Additionally, since adding new candidate answers affects the novelty scores of previously scored answers, we recalculate and update the novelty scores M^N(A_i) for all previously scored answers in each scoring round.

### 6.3 SetPO（arXiv 2602.1062）的多样性目标（逐字）

> To the best of our knowledge, **SetPO is the first to introduce an explicit set-level diversity objective.** Distinct from traditional pairwise methods, our approach adopts a distributional perspective: **it evaluates the holistic diversity of the entire sampled set by aggregating semantic similarities**, rather than focusing on isolated local differences.
>
> We incorporate a **leave-one-out marginal contribution mechanism** into policy optimization, where each trajectory is rewarded based on its impact on the set's diversity. Our theoretical analysis demonstrates the **anti-redundant** nature of this estimator, showing that it assigns higher marginal value to rarer samples.

### 6.4 MOAE（arXiv 2609.05992）的目标（逐字，摘要）

> Existing methods have considered multiple objectives, but many **collapse heterogeneous measurements into a fixed scalar score**. Such scalarization depends on metric normalization and preference weights and may discard candidates that represent useful deployment trade-offs. We introduce Multi-Objective Agent Evolution (MOAE), which organizes iterative in-context refinement as a **Pareto-preserving evolutionary search over complete agent rollouts**. Given a limited rollout budget, MOAE maintains an **empirical archive of non-dominated candidates**, uses **objective-specific diagnostics** to guide offspring generation, and applies **constraint-aware selection only at deployment**. This separates candidate preservation during search from the preference used to return a final solution. The procedure requires no parameter updates and **allows each objective to be replaced by any measurable property, which we instantiate as task performance, trajectory quality, and safety.**

### 6.5 Heuresis（arXiv 2606.25198）的目标与关键结论（逐字，摘要 + 正文）

> We implement six search strategies: a greedy baseline, two archive-based (MAP-Elites, Go-Explore), one evolutionary (Islands), and two divergent (Curiosity, Omni), and evaluate them across **three axes (Quality, Diversity, and Novelty)** ...
> We find that **completely novel ideas are rare**. No idea across our scored runs is rated as "Original" ... Moreover, **novel ideas never approach the highest-performing known-recipe scores**. ...
> Our results show that while current search and Quality-Diversity strategies **enable us to steer where the generated ideas land on the quality, diversity, and novelty axes, they do not expand the quality–novelty frontier.**

关键机制（正文逐字，节选）：
> **Divergent Objectives** replace task fitness with an exploration-rewarding signal. ... novelty search drops the objective entirely ...
> A recent line replaces the hand-crafted signal with a foundation-model judge: **OMNI scores candidates against context as a Model of Interestingness**, extended to archive-aware rejection in OMNI-EPIC
> **Diversity-preserving archives** reframe search as illuminating a behaviour space. **MAP-Elites maintains a grid of behaviourally distinct elites** ...

多样性度量（正文逐字）：
> Diversity is measured in the embedding space of accepted ideas. We embed each idea's plan with gemini-embedding-001 ... For every pair of in-strategy ideas we compute the **cosine distance** and report the resulting per-strategy distribution, summarized by its median.

奖励伪造（正文逐字，节选）：
> We also observed agents resorting to a variety of **reward-hacking techniques** during execution (**40 confirmed fabrications across 1,628 scored runs**), and detecting them was necessary to keep the search faithful to the task.

### 6.6 DDO（arXiv 2609.10052）的目标（逐字，二手摘要的 arXiv 原文转述）

> **Direct Diversity Optimization (DDO)** ... consists of two main components: **Divergence-Tree Collection (DTC)**: Instead of just training on successful trajectories, DTC "rewinds" a successful agent to various decision points. It then uses an expert model to explore alternative actions. If these alternatives also lead to success, they are added to a "branch set" rooted at that specific state. ... **Reference-Relative Target-Odds Objective (RTO)**: Standard preference objectives usually try to pick one winner. RTO, instead, **treats all successful branches in a set as valid**. It defines a target distribution over these successful alternatives (often based on a reference model) and trains the agent to match the "log-odds" of these branches. This prevents the model from putting all its probability mass on just one path.

> The authors argue that agents need **successful strategy coverage**: the ability to realize multiple distinct ways to reach a goal from the same starting state.

⚠️ 上面这段出自二手聚合站 `lacuna.tiptreesystems.com`，**我只核了 arXiv id / 标题 / 作者**，**没有读 arXiv 原文**。要引用具体数字前必须自己读原文。

### 6.7 DMPO（arXiv 2605.19461）的机制解释（逐字，arXiv HTML 正文）

> On-policy reinforcement learning methods like GRPO suffer from mode collapse: they exhibit **reduced solution diversity**, concentrating probability mass on a single solution once discovered and ceasing exploration of alternative strategies. We show this stems from **reverse KL minimization's mode-seeking behavior**, which reinforces the first high-reward trajectory found rather than maintaining a distribution over multiple diverse solutions.

> Standard policy gradient methods like GRPO do not include explicit entropy regularization, corresponding to α→0. In this limit, the target becomes p*(τ)∝**I[τ=argmax r(τ)]**—a Dirac delta on the highest-reward trajectory. Thus, **policy gradient methods implicitly minimize reverse KL, inheriting its mode-seeking behavior.**

> In contrast, **forward KL** divergence D_KL(p*‖π_θ), which is **mode-covering**. Forward KL penalizes placing low probability where the target has high probability, forcing the policy to cover all modes of p* and **preventing mode collapse**.

> DMPO circumvents this challenge by operating at the group level: for each group of sampled trajectories, we construct a **target distribution proportional to their rewards (a Boltzmann distribution)** and explicitly align the policy distribution to this target.

### 6.8 Reaching Beyond the Mode（arXiv 2603.24844）——与"答案中庸"最直接对口

> Given a question, a language model (LM) implicitly encodes a **distribution over possible answers**. In practice, **post-training procedures for LMs often collapse this distribution onto a single dominant mode**. While this is generally not a problem for benchmark-style evaluations that assume one correct answer, many real-world tasks inherently involve multiple valid answers or irreducible uncertainty. ... We would like LMs to generate **multiple plausible hypotheses**, ideally with confidence estimates for each one, and without computationally intensive repeated sampling to generate non-modal answers.

### 6.9 SwarmResearch（arXiv 2607.02807）——**架构级**多样性（不是目标函数级）

> 1. **Context isolation** is the mechanism, not just a side effect of branching. When Search Agents cannot see each other's work, they cannot drift toward consensus. For any multi-agent system where you are worried that agents all arrive at the same answer, the question to ask is not "what model are we using?" but "**what can each one see?**"

（此条出自二手聚合站，arXiv id / 标题 / 作者已用 arXiv API 核过；"13 of 15" 等数字**未核**。）

---

## 7. 引用清单（建议直接抄这一段）

```
Yu Shang, Yu Li, Keyu Zhao, Likai Ma, Jiahe Liu, Fengli Xu, Yong Li.
"AgentSquare: Automatic LLM Agent Search in Modular Design Space."
arXiv:2410.06153v3 (cs.CL), v1 2024-10-08, v3 2025-02-27. 25 pages.
Code: https://github.com/tsinghua-fib-lab/AgentSquare  (branch: main)

Sebastián Andrés Mayorquín Posadas, Julio Vega.
"Thinking Is Not Enough: The B* Expansion Technique for Enhancing Autonomous LLM Agents."
Expert Systems 43(8): e70333, 2026-06-18. DOI 10.1111/exsy.70333
Code: https://github.com/SamthinkGit/Bstar-Expansion  (branch: master)

Chenyi Li, Yuan Zhang, Bo Wang, Guoqing Ma, Wei Tang, Haoyang Huang, Nan Duan.
"SetPO: Set-Level Policy Optimization for Diversity-Preserving LLM Reasoning."
arXiv:2602.1062, 2026-02-01.

Biqing Qi, Zhouyi Qian, Yiang Luo, Junqi Gao, Dong Li, Kaiyan Zhang, Bowen Zhou.
"Evolution of Thought: Diverse and High-Quality Reasoning via Multi-Objective Optimization."
arXiv:2412.7779, 2024-11-24.

Hengle Jiang, Qijun Cai, Ziying Luo, Ke Tang.
"MOAE: Multi-Objective Agent Evolution with Pareto-Preserving Search."
arXiv:2609.05992, 2026-09-05.

Antonis Antoniades, Deepak Nathani, Ritam Saha, Alfonso Amayuelas, Ivan Bercovich,
Zhaotian Weng, Vignesh Baskaran, Kunal Bhatia, William Yang Wang.
"Heuresis: Search Strategies for Autonomous AI Research Agents Across Quality, Diversity and Novelty."
arXiv:2606.25198, 2026-06-23.
```

**另外，AgentSquare 自己的参考文献里列了一条与我们最相关的前作**（我**未**单独核它的 arXiv id，只从 AgentSquare 原文逐字抄下）：

> Muhammad Umair Nasir, Sam Earle, Julian Togelius, Steven James, and Christopher Cleghorn.
> **Llmatic: Neural architecture search via large language models and quality diversity optimization.**
> In Proceedings of the Genetic and Evolutionary Computation Conference (GECCO), pp. 1110–1118, 2024.

⇒ **"用 QD 目标做 LLM 架构搜索"这件事，AgentSquare 自己引了 LLMATIC，但正文没采用。**
