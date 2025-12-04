import requests
import json
import logging
import mimetypes
from io import BytesIO

class DocServiceV2:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = None

    def get_tenant_token(self):
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

    # --- Enhanced Image Flow Methods ---

    def upload_file(self, file_name, file_data, parent_type, parent_node):
        """Generic upload to Drive"""
        token = self.get_tenant_token()
        if not token: return None

        url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        headers = {"Authorization": f"Bearer {token}"}
        
        files = {'file': (file_name, file_data, mimetypes.guess_type(file_name)[0] or 'application/octet-stream')}
        data = {
            'file_name': file_name,
            'parent_type': parent_type,
            'parent_node': parent_node,
            'size': len(file_data)
        }
        
        try:
            resp = requests.post(url, headers=headers, files=files, data=data)
            if resp.status_code == 200 and resp.json().get('code') == 0:
                return resp.json()['data']['file_token']
            else:
                logging.error(f"Upload failed: {resp.text}")
                return None
        except Exception as e:
            logging.error(f"Upload exception: {e}")
            return None

    def update_image_block(self, doc_id, block_id, file_token):
        """Step 3: Update the block with the real image token"""
        token = self.get_tenant_token()
        if not token: return False

        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{block_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        # https://open.feishu.cn/document/server-docs/docs/docx-v1/document-block/patch
        payload = {
            "replace_image": {
                "token": file_token
            }
        }
        
        try:
            resp = requests.patch(url, headers=headers, json=payload)
            if resp.status_code != 200:
                logging.error(f"Update block {block_id} failed: {resp.text}")
                return False
            return True
        except Exception as e:
            logging.error(f"Update block exception: {e}")
            return False

    # --- Block Creators ---
    
    def create_heading_block(self, text, level=2, link_url=None):
        text_run = {"content": text}
        if link_url:
            text_run["text_element_style"] = {"link": {"url": link_url}}
        
        return {
            "block_type": level + 2, 
            f"heading{level}": {"elements": [{"type": 1, "text_run": text_run}]}
        }

    def create_text_block(self, text, link_url=None):
        text_run = {"content": text}
        if link_url:
            text_run["text_element_style"] = {"link": {"url": link_url}}
            
        return {
            "block_type": 2,
            "text": {"elements": [{"type": 1, "text_run": text_run}]}
        }

    def create_quote_block(self, text):
        return {
            "block_type": 11, 
            "quote": {"elements": [{"type": 1, "text_run": {"content": text}}]}
        }

    def create_divider_block(self):
        return {
            "block_type": 22, 
            "divider": {}
        }

    def create_image_block(self, placeholder_token):
        # Creates a block with a placeholder token (Step 1)
        img_prop = {}
        if placeholder_token:
            img_prop["token"] = placeholder_token
        
        return {
            "block_type": 27,
            "image": img_prop
        }

    def add_content(self, doc_id, blocks):
        """
        Add content and RETURN the list of created block info (including block_ids).
        """
        token = self.get_tenant_token()
        if not token: return None
        
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        created_blocks_info = []
        
        # Batch insert (Limit 50)
        batch_size = 50
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i:i+batch_size]
            payload = {"children": batch}
            
            try:
                resp = requests.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    logging.error(f"Add blocks failed: {resp.text}")
                    continue # Try next batch? Or abort?
                
                data = resp.json().get("data", {})
                children = data.get("children", [])
                created_blocks_info.extend(children)
                
            except Exception as e:
                 logging.error(f"Add blocks exception: {e}")

        return created_blocks_info

    def transfer_ownership(self, doc_id, owner_open_id):
        # (Keep same as before)
        token = self.get_tenant_token()
        if not token: return False
        url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_id}/transfer_owner"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
        payload = {"member_type": "openid", "member_id": owner_open_id, "remove_old_owner": True}
        try:
            requests.post(url, headers=headers, json=payload)
            return True
        except: return False
