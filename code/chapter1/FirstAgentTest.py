# ============================================================================
# 文件：FirstAgentTest.py
# 功能：一个最简单的「工具调用型智能体（Tool-Using Agent）」完整示例
# ----------------------------------------------------------------------------
# 这个程序演示了智能体最核心的工作原理，也就是
#   「思考 → 行动 → 观察」的循环（Thought-Action-Observation Loop）：
#
#   1. Thought（思考）    ：让大模型阅读当前已知信息，思考下一步该做什么；
#   2. Action（行动）     ：大模型输出一个「动作」，可能是调用某个工具，也可能是结束；
#   3. Observation（观察） ：执行该动作后得到的真实结果，再喂回给大模型；
#   4. 重复 1~3，直到大模型认为信息足够，输出最终答案。
#
# 在这个例子中，智能体扮演「旅行助手」，它手里有两个工具可以调用：
#   - get_weather(city)             ：查询某个城市的实时天气；
#   - get_attraction(city, weather) ：根据天气推荐旅游景点。
# 用户的问题是「查北京天气，再推荐景点」，智能体需要自己决定调用顺序，
# 并在获得足够信息后，给出综合性的最终回答。
# ============================================================================


# ----------------------------------------------------------------------------
# 一、系统提示词（System Prompt）
# ----------------------------------------------------------------------------
# 这段文字会作为「系统消息」发给大模型，用来给模型设定角色、交代可用工具、
# 并严格规定它每轮的输出格式。智能体之所以能「按格式输出、按流程调用工具」，
# 靠的就是这一段提示词的约束。
# ----------------------------------------------------------------------------
AGENT_SYSTEM_PROMPT = """
你是一个智能旅行助手。你的任务是分析用户的请求，并使用可用工具一步步地解决问题。

# 可用工具:
- `get_weather(city: str)`: 查询指定城市的实时天气。
- `get_attraction(city: str, weather: str)`: 根据城市和天气搜索推荐的旅游景点。

# 输出格式要求:
你的每次回复必须严格遵循以下格式，包含一对Thought和Action：

Thought: [你的思考过程和下一步计划]
Action: [你要执行的具体行动]

Action的格式必须是以下之一：
1. 调用工具：function_name(arg_name="arg_value")
2. 结束任务：Finish[最终答案]

# 重要提示:
- 每次只输出一对Thought-Action
- Action必须在同一行，不要换行
- 当收集到足够信息可以回答用户问题时，必须使用 Action: Finish[最终答案] 格式结束

请开始吧！
"""


# ----------------------------------------------------------------------------
# 二、工具 1：get_weather —— 查询天气
# ----------------------------------------------------------------------------
# 智能体本身不会「知道」天气，它必须借助外部工具获取真实数据。
# 这个函数就是对 wttr.in 这个免费天气 API 的封装，属于智能体的「手」。
# ----------------------------------------------------------------------------
import requests

def get_weather(city: str) -> str:
    """
    通过调用 wttr.in API 查询真实的天气信息。

    参数：
        city: 城市名（如 "Beijing"、"北京"）。
    返回：
        一段描述该城市当前天气的自然语言字符串。
    """
    # wttr.in 支持直接返回 JSON 数据，format=j1 表示要 JSON 格式
    url = f"https://wttr.in/{city}?format=j1"

    try:
        # 发起网络请求
        response = requests.get(url)
        # 如果状态码不是 200，会抛出异常（比如城市名无效返回 404）
        response.raise_for_status()
        # 把返回的 JSON 字符串解析成 Python 字典
        data = response.json()

        # 从嵌套的 JSON 结构里取出「当前天气」这一块
        current_condition = data['current_condition'][0]
        weather_desc = current_condition['weatherDesc'][0]['value']  # 天气描述，如 "Sunny"
        temp_c = current_condition['temp_C']                          # 气温（摄氏度）

        # 把原始数据整理成一句自然语言，方便后续喂回给大模型
        return f"{city}当前天气：{weather_desc}，气温{temp_c}摄氏度"

    except requests.exceptions.RequestException as e:
        # 网络层面的错误（连不上、超时等）
        return f"错误：查询天气时遇到网络问题 - {e}"
    except (KeyError, IndexError) as e:
        # 数据解析层面的错误（字段不存在，通常是城市名无效导致）
        return f"错误：解析天气数据失败，可能是城市名称无效 - {e}"


# ----------------------------------------------------------------------------
# 三、工具 2：get_attraction —— 推荐景点
# ----------------------------------------------------------------------------
# 这个函数借助 Tavily 搜索 API，根据「城市 + 天气」去网上搜值得去的景点。
# 它演示了智能体的另一种能力：调用外部搜索服务获取实时、开放的信息。
# ----------------------------------------------------------------------------
import os
from tavily import TavilyClient

def get_attraction(city: str, weather: str) -> str:
    """
    根据城市和天气，使用 Tavily Search API 搜索并返回优化后的景点推荐。

    参数：
        city   : 城市名；
        weather: 天气描述（由 get_weather 的结果提供）。
    返回：
        基于搜索结果整理的景点推荐文本。
    """
    # 从环境变量中读取 Tavily 的 API 密钥（推荐做法，密钥不写死在代码里）
    api_key = os.environ.get("TAVILY_API_KEY")

    # 如果没有配置密钥，直接给出错误提示，避免后续调用报错
    if not api_key:
        return "错误：未配置TAVILY_API_KEY。"

    # 用密钥初始化 Tavily 客户端
    tavily = TavilyClient(api_key=api_key)

    # 把「城市 + 天气」拼成一个明确的搜索问题，提高搜索结果质量
    query = f"'{city}' 在'{weather}'天气下最值得去的旅游景点推荐及理由"

    try:
        # include_answer=True 会让 Tavily 额外返回一段基于搜索结果的总结性回答
        response = tavily.search(query=query, search_depth="basic", include_answer=True)

        # 优先使用 Tavily 直接生成的总结回答，它通常最干净、最接近用户想要的答案
        if response.get("answer"):
            return response["answer"]

        # 如果没有总结回答，就把原始搜索结果逐条格式化
        formatted_results = []
        for result in response.get("results", []):
            formatted_results.append(f"- {result['title']}: {result['content']}")

        # 如果连原始结果都没有，说明没搜到任何东西
        if not formatted_results:
            return "抱歉，没有找到相关的旅游景点推荐。"

        return "根据搜索，为您找到以下信息：\n" + "\n".join(formatted_results)

    except Exception as e:
        # 任何异常都转成字符串返回，保证主循环不会因此崩溃
        return f"错误：执行Tavily搜索时出现问题 - {e}"


# ----------------------------------------------------------------------------
# 四、工具注册表
# ----------------------------------------------------------------------------
# 把工具函数统一放进一个字典，键是「工具名」，值是「函数对象」。
# 这样主循环里只要拿到模型输出的工具名字符串，就能查表找到对应函数并调用，
# 而不需要写一堆 if/elif。后续想加新工具，也只需往这个字典里加一行。
# ----------------------------------------------------------------------------
available_tools = {
    "get_weather": get_weather,
    "get_attraction": get_attraction,
}


# ----------------------------------------------------------------------------
# 五、LLM 客户端封装
# ----------------------------------------------------------------------------
# 智能体的「大脑」是大语言模型。我们通过 OpenAI 官方 SDK 的接口来调用它。
# 因为现在很多国产模型（如智谱 GLM）都兼容 OpenAI 的接口格式，
# 所以只要改一下 base_url 和 api_key，就能无缝切换不同的模型服务。
# ----------------------------------------------------------------------------
from openai import OpenAI

class OpenAICompatibleClient:
    """
    一个用于调用任何兼容 OpenAI 接口的 LLM 服务的客户端。
    """
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        # 用给定的 base_url 和 api_key 创建真正的 OpenAI 客户端实例
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, prompt: str, system_prompt: str) -> str:
        """调用 LLM API 来生成回应。"""
        print("正在调用大语言模型...")
        try:
            # 构造消息列表：一条系统消息（角色设定）+ 一条用户消息（历史对话内容）
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ]
            # 调用 Chat Completion 接口，stream=False 表示一次性返回完整结果
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False
            )
            # 从返回结果里取出模型生成的文本
            answer = response.choices[0].message.content
            print("大语言模型响应成功。")
            return answer
        except Exception as e:
            # 调用失败时返回一段错误文本，而不是让程序崩溃，
            # 这样主循环还能继续把错误信息作为 Observation 喂回去
            print(f"调用LLM API时发生错误: {e}")
            return "错误：调用语言模型服务时出错。"


import re

# ----------------------------------------------------------------------------
# 六、配置：从 .env 读取密钥和模型信息
# ----------------------------------------------------------------------------
# 密钥、模型名、接口地址都属于敏感或易变的信息，不应该硬编码在源码里。
# 这里用 python-dotenv 从同目录下的 .env 文件读取，既安全又方便修改。
# ----------------------------------------------------------------------------
from pathlib import Path
from dotenv import load_dotenv

# Path(__file__).resolve().parent 定位到本文件所在目录，加载该目录下的 .env
load_dotenv(Path(__file__).resolve().parent / '.env')

API_KEY = os.environ.get('API_KEY')    # 大模型服务的 API 密钥
BASE_URL = os.environ.get('BASE_URL')  # 接口地址（智谱 Chat Completion 协议）
MODEL_ID = os.environ.get('MODEL_ID')  # 使用的模型名，如 glm-5
# TAVILY_API_KEY 不需要在这里读取，get_attraction 内部会用 os.environ.get 直接拿

# 用读取到的配置实例化 LLM 客户端
llm = OpenAICompatibleClient(
    model=MODEL_ID,
    api_key=API_KEY,
    base_url=BASE_URL
)


# ----------------------------------------------------------------------------
# 七、初始化对话
# ----------------------------------------------------------------------------
# prompt_history 是「对话历史」，它会被反复拼接到下一轮的大模型输入里，
# 从而实现「记忆」：模型能看到之前每一步的 Thought、Action 和 Observation。
# ----------------------------------------------------------------------------
user_prompt = "你好，请帮我查询一下今天北京的天气，然后根据天气推荐一个合适的旅游景点。"
prompt_history = [f"用户请求: {user_prompt}"]

print(f"用户输入: {user_prompt}\n" + "=" * 40)


# ----------------------------------------------------------------------------
# 八、主循环：智能体的核心运行流程
# ----------------------------------------------------------------------------
# 下面是整个智能体的「心脏」——一个最多执行 5 轮的循环。
# 每一轮都严格按「思考 → 行动 → 观察」推进：
#   1. 把历史记录拼成 prompt，交给大模型；
#   2. 大模型输出一对 Thought-Action；
#   3. 程序解析出 Action，要么调用工具，要么结束；
#   4. 把执行结果（Observation）追加进历史，进入下一轮。
# ----------------------------------------------------------------------------
for i in range(5):  # 最多循环 5 次，防止模型一直不结束导致死循环
    print(f"--- 循环 {i + 1} ---\n")

    # --- 3.1. 构建 Prompt ---
    # 把目前积累的所有历史（用户请求 + 过去的 Thought/Action/Observation）拼接成一段文本，
    # 作为本轮的用户消息。这是智能体「看到全部上下文」的关键。
    full_prompt = "\n".join(prompt_history)

    # --- 3.2. 调用 LLM 进行思考 ---
    llm_output = llm.generate(full_prompt, system_prompt=AGENT_SYSTEM_PROMPT)

    # 模型有时会「超纲」：一次性输出多对 Thought-Action，甚至自己脑补出 Observation。
    # 这里用正则截取「第一对完整的 Thought-Action」，保证后续解析只处理本轮该做的动作。
    # 正则含义：
    #   (Thought:.*?Action:.*?)                    非贪婪地匹配第一对 Thought 和 Action；
    #   (?= \n\s*(?:Thought:|Action:|Observation:) | \Z)  前瞻断言：截取到下一个
    #     Thought:/Action:/Observation: 出现之前，或者字符串末尾；
    #   re.DOTALL 让 . 也能匹配换行，因为 Action 内容可能跨行。
    match = re.search(r'(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)', llm_output, re.DOTALL)
    if match:
        truncated = match.group(1).strip()
        if truncated != llm_output.strip():
            llm_output = truncated
            print("已截断多余的 Thought-Action 对")
    print(f"模型输出:\n{llm_output}\n")
    prompt_history.append(llm_output)

    # --- 3.3. 解析并执行 Action ---
    # 从模型输出里提取 "Action: " 后面的内容。re.DOTALL 允许内容跨行。
    action_match = re.search(r"Action: (.*)", llm_output, re.DOTALL)
    if not action_match:
        # 模型没有输出 Action 字段，把错误信息作为 Observation 喂回去，让它自我纠正
        observation = "错误: 未能解析到 Action 字段。请确保你的回复严格遵循 'Thought: ... Action: ...' 的格式。"
        observation_str = f"Observation: {observation}"
        print(f"{observation_str}\n" + "=" * 40)
        prompt_history.append(observation_str)
        continue  # 直接进入下一轮
    action_str = action_match.group(1).strip()

    # 情况 A：模型认为任务已完成，输出 Finish[...]
    if action_str.startswith("Finish"):
        # 兼容多种结束写法：Finish[答案] / Finish(答案) / Finish: 答案 / Finish 答案
        m = re.match(r"Finish\s*[\[\(](.*)[\]\)]", action_str, re.DOTALL)
        if m:
            final_answer = m.group(1).strip()
        else:
            # 匹配不到方括号/圆括号时，去掉 "Finish" 前缀并清理首尾符号，剩余即为答案
            final_answer = action_str[len("Finish"):].strip(" :：")
        print(f"任务完成，最终答案: {final_answer}")
        break  # 得到最终答案，结束整个循环

    # 情况 B：模型想要调用某个工具，输出 function_name(arg="value")
    # 正则 (\w+)\((.*)\) 把 "get_weather(city=\"北京\")" 拆成：
    #   group(1) = "get_weather"（工具名）
    #   group(2) = "city=\"北京\""（参数字符串）
    tool_match = re.search(r"(\w+)\((.*)\)", action_str)
    if not tool_match:
        # 工具调用格式也不对，同样把错误喂回去，让模型重试
        observation = f"错误：无法解析工具调用，请使用 function_name(arg_name=\"arg_value\") 的格式。收到: {action_str}"
        observation_str = f"Observation: {observation}"
        print(f"{observation_str}\n" + "=" * 40)
        prompt_history.append(observation_str)
        continue
    tool_name = tool_match.group(1)
    args_str = tool_match.group(2)

    # 从参数字符串里提取所有 key="value" 键值对，转成字典。
    # 例如 'city="北京" weather="晴"' -> {'city': '北京', 'weather': '晴'}
    kwargs = dict(re.findall(r'(\w+)="([^"]*)"', args_str))

    # 查工具注册表：如果工具存在就调用它，否则报「未定义的工具」
    if tool_name in available_tools:
        observation = available_tools[tool_name](**kwargs)  # **kwargs 把字典展开成关键字参数
    else:
        observation = f"错误：未定义的工具 '{tool_name}'"

    # --- 3.4. 记录观察结果（Observation） ---
    # 无论工具调用成功还是失败，都把结果包装成 "Observation: ..." 追加进历史，
    # 这样下一轮大模型就能看到「刚才那个动作带来了什么结果」，据此继续思考。
    observation_str = f"Observation: {observation}"
    print(f"{observation_str}\n" + "=" * 40)
    prompt_history.append(observation_str)
