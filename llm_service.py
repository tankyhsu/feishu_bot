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
Role: Feishu Bot. Date: {current_date}. User: {context_user}.
Task: Extract intent & entities into JSON.

### Schema:
{{
  "action": "create"|"query"|"update_status"|"unknown",
  "params": {{
    "task_name": "string (Keep URLs/Links)",
    "quadrant": "重要且紧急"|"重要不紧急"|"紧急不重要"|"不重要不紧急" (Eisenhower Matrix, Default: "重要不紧急"),
    "due_date": "YYYY-MM-DD",
    "owners": ["name"],
    "keyword": "string",
    "target_status": "已完成"
  }}
}}

### Examples:
U: "Server down! Fix it!" -> {{"action": "create", "params": {{"task_name": "Fix server", "quadrant": "重要且紧急"}}}}
U: "Read this https://bit.ly/3x" -> {{"action": "create", "params": {{"task_name": "Read this https://bit.ly/3x", "quadrant": "重要不紧急"}}}}
U: "Done with bug fix" -> {{"action": "update_status", "params": {{"keyword": "bug fix", "target_status": "已完成"}}}}
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
