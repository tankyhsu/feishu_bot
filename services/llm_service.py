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
### ROLE
You are an intelligent Project Management Assistant for a Feishu/Lark group chat.
Current Date: {current_date}
User: {context_user}

### GOAL
Analyze the user's natural language input, determine the Intent (Create, Update, or Query), and extract relevant entities into a strict JSON format.

### STEP 1: INTENT CLASSIFICATION (Reasoning Logic)
1. **update_status**:
   - Trigger: User indicates a task is completed, finished, resolved, or closed.
   - Keywords (implied included): "DONE", "FIXED", "CLOSED", "MERGED", "DEPLOYED", "已完成", "搞定了", "修好了", "上线了", "代码提交了", "已经", "完成了", "已", "搞定", "解决".
   - Focus: The user is reporting the **result** of an action.
2. **query**:
   - Trigger: User is asking for information.
   - Keywords: "list", "what", "show me", "我的任务", "还有啥", "进度".
3. **create**: (DEFAULT)
   - Trigger: User defines work TO BE DONE, assigns a task, or records an idea.
   - Focus: Future actions, imperatives ("Fix this", "Buy that", "Remember to...").

### STEP 2: ENTITY EXTRACTION RULES
1. **task_name**:
   - Keep the full meaningful content, including URLs.
   - If there is a URL, keeping it is CRITICAL.
2. **quadrant** (Eisenhower Matrix Inference):
   - "重要且紧急": Words like "ASAP", "Crash", "Bug", "Online", "紧急", "报错", "马上".
   - "重要不紧急": Strategic work, "Plan", "Review", "Research", "方案", "调研".
   - "紧急不重要": Admin tasks, "Send email", "Schedule meeting".
   - "不重要不紧急": "Read article", "Check out", "Casual ideas".
   - *Default to "重要不紧急" if unsure.*
3. **due_date**:
   - Convert relative dates (e.g., "next Friday", "tomorrow", "下周一") to `YYYY-MM-DD` based on `Current Date`.
   - If no date is mentioned, return `null`.
4. **keyword** (For updates):
   - Extract the **core subject** of the task being marked as done.
   - Example: "Login bug is fixed" -> keyword: "Login bug" (Remove status words like "fixed").
5. **create_native_task**:
   - **Boolean**. Defaults to **false**.
   - Set to **true** ONLY if the user explicitly mentions keywords like: "task", "reminder", "alert", "群任务", "提醒我", "建个任务".

### OUTPUT SCHEMA (Strict JSON)
{{
  "action": "create" | "query" | "update_status",
  "params": {{
    "task_name": "string (Full content)",
    "quadrant": "重要且紧急" | "重要不紧急" | "紧急不重要" | "不重要不紧急",
    "due_date": "YYYY-MM-DD" or null,
    "owners": ["string (Extract @mentions or names if specifically assigned)"],
    "keyword": "string (The target task subject for updates)",
    "target_status": "已完成",
    "create_native_task": boolean
  }}
}}

### FEW-SHOT EXAMPLES
U: "Server is down! Fix it immediately!"
A: {{"action": "create", "params": {{"task_name": "Fix server down issue", "quadrant": "重要且紧急", "due_date": "{current_date}", "create_native_task": false}}}}

U: "I have fixed the login bug on iOS."
A: {{"action": "update_status", "params": {{"keyword": "login bug on iOS", "target_status": "已完成"}}}}

U: "把 '首页UI优化' 那个任务搞定了"
A: {{"action": "update_status", "params": {{"keyword": "首页UI优化", "target_status": "已完成"}}}}

U: "Read this article https://bit.ly/3x sometime next week, create a reminder."
A: {{"action": "create", "params": {{"task_name": "Read this article https://bit.ly/3x", "quadrant": "重要不紧急", "due_date": "(Calculate date for next week)", "create_native_task": true}}}}

U: "建个群任务：明天下午开会"
A: {{"action": "create", "params": {{"task_name": "明天下午开会", "quadrant": "紧急不重要", "due_date": "(Calculate date for tomorrow)", "create_native_task": true}}}}

U: "What tasks do I have?"
A: {{"action": "query", "params": {{}}}}
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

    def analyze_rss(self, articles_text):
        """
        Analyze RSS articles and return structured JSON.
        """
        if not self.client:
            return None

        system_prompt = """
        You are an AI RSS Assistant.
        Your task is to analyze a list of articles and return a STRICT JSON object.

        Task:
        1. Filter out ads, recruiting, or low-value content.
        2. For valid articles:
           - Rewrite title to be short and catchy (Chinese).
           - Classify the category.
           - Keep track of the original index.
        3. Generate a "daily_insight" (Chinese) based on the overall trend.

        Output Format (JSON):
        {
            "daily_insight": "今日AI趋势...",
            "articles": [
                {
                    "original_index": 1, 
                    "title": "中文标题",
                    "category": "AI / Tech / Life"
                }
            ]
        }
        """

        user_prompt = f"Articles:\n{articles_text}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logging.error(f"❌ RSS Analysis Error: {e}")
            return None
