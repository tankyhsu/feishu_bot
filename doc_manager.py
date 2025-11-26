import requests
import json
import logging

class DocManager:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = None

    def get_tenant_token(self):
        # Simple token cache could be added here, but for now just fetch
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret})
        if resp.status_code == 200:
            return resp.json().get("tenant_access_token")
        logging.error(f"Failed to get token: {resp.text}")
        return None

    def create_document(self, title="Meeting Minutes"):
        token = self.get_tenant_token()
        if not token: return None
        
        url = "https://open.feishu.cn/open-apis/docx/v1/documents"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {"title": title}
        
        try:
            resp = requests.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                logging.error(f"Create doc failed: {resp.text}")
                return None
            return resp.json().get("data", {}).get("document", {}).get("document_id")
        except Exception as e:
            logging.error(f"Create doc exception: {e}")
            return None

    def parse_markdown_to_blocks(self, text):
        blocks = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            block = None
            
            # Heading 1
            if line.startswith('# '):
                content = line[2:].strip()
                block = {
                    "block_type": 3,
                    "heading1": {"elements": [{"type": 1, "text_run": {"content": content}}]}}
            # Heading 2
            elif line.startswith('## '):
                content = line[3:].strip()
                block = {
                    "block_type": 4,
                    "heading2": {"elements": [{"type": 1, "text_run": {"content": content}}]}}
            # Heading 3
            elif line.startswith('### '):
                content = line[4:].strip()
                block = {
                    "block_type": 5,
                    "heading3": {"elements": [{"type": 1, "text_run": {"content": content}}]}}
            # Bullet List
            elif line.startswith('- ') or line.startswith('* '):
                content = line[2:].strip()
                block = {
                    "block_type": 12,
                    "bullet": {"elements": [{"type": 1, "text_run": {"content": content}}]}}
            # Ordered List (Simple check)
            elif len(line) > 2 and line[0].isdigit() and line[1] == '.' and line[2] == ' ':
                 content = line.split(' ', 1)[1].strip()
                 block = {
                    "block_type": 13,
                    "ordered": {"elements": [{"type": 1, "text_run": {"content": content}}]}}
            # Default Text
            else:
                block = {
                    "block_type": 2,
                    "text": {"elements": [{"type": 1, "text_run": {"content": line}}]}}
            
            if block:
                blocks.append(block)
                
        return blocks

    def add_content(self, doc_id, markdown_text):
        token = self.get_tenant_token()
        if not token: return False
        
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        # Parse blocks
        children = self.parse_markdown_to_blocks(markdown_text)
        if not children: return True
        
        # Batch insert (Limit is usually 50 blocks per request, simple paging)
        batch_size = 50
        for i in range(0, len(children), batch_size):
            batch = children[i:i+batch_size]
            payload = {"children": batch}
            
            try:
                resp = requests.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    logging.error(f"Add blocks failed: {resp.text}")
            except Exception as e:
                 logging.error(f"Add blocks exception: {e}")

        return True

    def transfer_ownership(self, doc_id, owner_open_id):
        token = self.get_tenant_token()
        if not token: return False

        url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_id}/transfer_owner"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {
            "member_type": "openid", # or "unionid", "userid"
            "member_id": owner_open_id,
            "remove_old_owner": True # Optional, usually set to True if truly transferring
        }

        try:
            resp = requests.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                logging.error(f"Transfer ownership failed for doc {doc_id} to {owner_open_id}: {resp.text}")
                return False
            data = resp.json()
            if data.get("code") != 0:
                logging.error(f"Transfer ownership API error: {data}")
                return False
            return True
        except Exception as e:
            logging.error(f"Transfer ownership exception: {e}")
            return False
