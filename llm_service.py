import json
import logging
import os
from datetime import datetime
from openai import OpenAI

# 配置日志
logging.basicConfig(level=logging.INFO)

class LLMParser:
    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model or "gpt-3.5-turbo" # Default fallback, user can change to deepseek-chat etc.
        self.client = None
        
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                logging.info(f"🧠 LLM Client initialized (Model: {self.model})")
            except Exception as e:
                logging.error(f"❌ LLM Init failed: {e}")

    def parse(self, text, context_user="unknown"):
        """
        解析用户指令，返回结构化 JSON
        """
        # 1. 如果没有 LLM 客户端，返回 None (让调用者回退到正则)
        if not self.client:
            logging.warning("⚠️ No LLM Client active. Fallback to Regex.")
            return None

        # 2. 构建 Prompt
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        system_prompt = f"""
You are a smart project assistant for a Feishu/Lark bot.
Current Date: {current_date}
Current User: {context_user}

Your goal is to classify the user's intent and extract entities into JSON.

### Intents (Actions):
1. "create": Create a new task.
2. "query": Query/List tasks.
3. "update_status": Update a task's status (e.g. mark as done).
4. "unknown": Cannot understand.

### Output Schema (JSON):
{{
  "action": "create" | "query" | "update_status" | "unknown",
  "params": {{
    "task_name": "string (for create)",
    "quadrant": "重要且紧急" | "重要不紧急" | "紧急不重要" | "不重要不紧急" (Infer from context. Default: "重要不紧急"),
    "due_date": "YYYY-MM-DD",
    "owners": ["name1"],
    "keyword": "string",
    "target_status": "已完成" | "待办" | "进行中"
  }}
}}

### Matrix Logic (Eisenhower):
- **重要且紧急**: Critical bugs, deadlines today/tomorrow, boss requests, server down.
- **重要不紧急**: New features, long-term plans, refactoring, learning.
- **紧急不重要**: Meetings, interruptions, minor emails, helping others with small tasks.
- **不重要不紧急**: Browsing news, trivial tasks.

### Examples:
User: "服务器炸了！快修！"
JSON: {{"action": "create", "params": {{"task_name": "修复服务器故障", "quadrant": "重要且紧急"}}}}

User: "下个季度我们要规划一下新的架构"
JSON: {{"action": "create", "params": {{"task_name": "规划新架构", "quadrant": "重要不紧急"}}}}

User: "帮我拿一下快递"
JSON: {{"action": "create", "params": {{"task_name": "拿快递", "quadrant": "紧急不重要"}}}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"}, # Require JSON mode if supported
                temperature=0.1
            )
            content = response.choices[0].message.content
            result = json.loads(content)
            logging.info(f"🧠 LLM Analysis: {result}")
            return result
        
        except Exception as e:
            logging.error(f"❌ LLM Inference Error: {e}")
            return None
