import logging
import re
import requests
from openai import OpenAI

# 配置日志
logging.basicConfig(level=logging.INFO)

class MinutesSummarizer:
    def __init__(self, app_id, app_secret, llm_key, llm_base, llm_model):
        self.app_id = app_id
        self.app_secret = app_secret
        self.llm_client = OpenAI(api_key=llm_key, base_url=llm_base)
        self.llm_model = llm_model

    def get_tenant_token(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret})
        if resp.status_code == 200:
            return resp.json().get("tenant_access_token")
        return None

    def extract_minutes_token(self, text):
        # 宽松匹配: 只要包含 /minutes/ 且后面跟着 token 即可
        # 兼容 meetings.feishu.cn, www.feishu.cn, 企业自定义域名
        pattern = r"/minutes/([a-zA-Z0-9]+)"
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        return None

    def _format_time(self, ms):
        try:
            seconds = int(ms) // 1000
            m, s = divmod(seconds, 60)
            return f"{m:02d}:{s:02d}"
        except:
            return "00:00"

    def fetch_subtitle(self, token):
        access_token = self.get_tenant_token()
        if not access_token: return None
        
        # Use the new transcript endpoint
        url = f"https://open.feishu.cn/open-apis/minutes/v1/minutes/{token}/transcript"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                logging.error(f"❌ 获取妙记失败: Code {resp.status_code} - {resp.text}")
                return None
            
            # Try to parse JSON
            try:
                data = resp.json()
                if data.get("code") != 0:
                    logging.error(f"❌ 获取妙记API错误: {data}")
                    return None
                    
                resp_data = data.get("data", {})
                
                # 1. Try to extract structured data with timestamps
                # Potential fields: sentences, paragraph_list, list
                candidates = ["sentences", "paragraph_list", "list"]
                items = []
                for key in candidates:
                    if key in resp_data:
                        items = resp_data[key]
                        break
                
                if items and isinstance(items, list):
                    full_text_with_time = []
                    for item in items:
                        content = item.get("content", "")
                        # Timestamp fields can be start_time, start, stop_time, etc.
                        start_ms = item.get("start_time") or item.get("start") or 0
                        time_str = self._format_time(start_ms)
                        full_text_with_time.append(f"[{time_str}] {content}")
                    return "\n".join(full_text_with_time)

                # 2. Fallback to plain text fields if no list found
                if "content" in resp_data:
                    return resp_data["content"]
                if "text" in resp_data:
                    return resp_data["text"]
                
                # 3. Fallback: Return the string representation
                return f"RAW_JSON_RESPONSE: {resp.text}"
                
            except Exception:
                return resp.text # Not JSON? Return raw text
                
        except Exception as e:
            logging.error(f"❌ 获取妙记异常: {e}")
            return None

    def summarize(self, text):
        if not text: return {"title": "无标题", "content": "❌ 无法获取内容"}
        
        prompt = """
你是一个专业的会议纪要秘书。请根据以下会议录音文本（包含时间戳），整理出一份结构化的会议纪要。

请务必严格按照以下 JSON 格式返回结果（不要包含 markdown 代码块标记，直接返回 JSON）：

{
    "title": "一句话概括会议主题（15字以内，作为文件名）",
    "content": "这里是完整的 Markdown 格式会议纪要内容，包含以下部分：\n1. **📌 核心议题**: ...\n2. **📝 关键细节**: ...\n3. **⏱️ 时间线回顾**: 按照话题切换，列出关键节点。格式如：`00:00 - 05:30 开场介绍及背景同步...`\n4. **✅ 待办事项 (Action Items)**: ...\n5. **💡 关键决策**: ..."
}

### 录音文本:
"""
        content_input = text[:15000] 
        try:
            resp = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": content_input}
                ],
                temperature=0.3,
                response_format={"type": "json_object"} 
            )
            
            import json
            try:
                result = json.loads(resp.choices[0].message.content)
                return result
            except json.JSONDecodeError:
                # Fallback if LLM doesn't return valid JSON
                raw_content = resp.choices[0].message.content
                return {
                    "title": "会议纪要",
                    "content": raw_content
                }

        except Exception as e:
            return {"title": "错误", "content": f"❌ AI 总结失败: {e}"}

