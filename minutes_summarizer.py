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
                
                # Try different known fields
                if "content" in resp_data:
                    return resp_data["content"]
                if "text" in resp_data:
                    return resp_data["text"]
                if "paragraph_list" in resp_data: # Some APIs use this
                    return "\n".join([p.get("content","") for p in resp_data["paragraph_list"]])
                
                # Fallback: Return the string representation to help debugging
                return f"RAW_JSON_RESPONSE: {resp.text}"
                
            except Exception:
                return resp.text # Not JSON? Return raw text
                
        except Exception as e:
            logging.error(f"❌ 获取妙记异常: {e}")
            return None

    def summarize(self, text):
        if not text: return "❌ 无法获取内容"
        
        prompt = """
你是一个专业的会议纪要秘书。请根据以下会议录音文本，整理出一份结构化的会议纪要。

### 格式要求 (Markdown):
1. **📌 核心议题**: 一句话概括会议主题。
2. **📝 关键细节**: 列出3-5个讨论重点。
3. **✅ 待办事项 (Action Items)**: 具体的后续行动及负责人。
4. **💡 关键决策**: 会议达成的结论。

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
                temperature=0.3
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"❌ AI 总结失败: {e}"

