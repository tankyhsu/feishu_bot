import logging
import requests
from datetime import datetime
from lark_oapi.api.bitable.v1.model import (
    CreateAppTableRecordRequest, AppTableRecord,
    SearchAppTableRecordRequest, SearchAppTableRecordRequestBody,
    UpdateAppTableRecordRequest
)

class TaskService:
    def __init__(self, client, config):
        self.client = client
        self.config = config
        self.app_token = config.BITABLE_APP_TOKEN
        self.table_id = config.TABLE_ID
        self.app_id = config.APP_ID
        self.app_secret = config.APP_SECRET
        self.bot_open_id = None

    def get_bot_id(self):
        # Lazy load Bot ID
        if not self.bot_open_id:
            try:
                url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
                t_resp = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret})
                token = t_resp.json().get("tenant_access_token")
                
                resp = requests.get("https://open.feishu.cn/open-apis/bot/v3/info", 
                                  headers={"Authorization": f"Bearer {token}"})
                if resp.status_code == 200:
                    self.bot_open_id = resp.json().get("data", {}).get("bot", {}).get("open_id")
            except: pass
        return self.bot_open_id

    def get_text_value(self, field_value):
        if isinstance(field_value, str): return field_value
        if isinstance(field_value, list) and len(field_value) > 0:
            if isinstance(field_value[0], dict) and "text" in field_value[0]:
                return "".join([item.get("text", "") for item in field_value])
        return str(field_value) if field_value else ""

    def handle_query(self, open_id):
        req = SearchAppTableRecordRequest.builder().app_token(self.app_token).table_id(self.table_id).request_body(SearchAppTableRecordRequestBody.builder().build()).build()
        resp = self.client.bitable.v1.app_table_record.search(req)
        if not resp.success(): return "❌ 查询失败"
        
        items = resp.data.items or []
        my_tasks = []
        for item in items:
            fields = item.fields
            if fields.get("状态") == "已完成": continue
            owners = fields.get("负责人", [])
            if any(o.get("id") == open_id for o in owners):
                my_tasks.append(item)
        
        my_tasks.sort(key=lambda x: x.fields.get("截止日期", 0) or 0, reverse=True)
        if not my_tasks: return "🎉 无待办任务"
        
        msg = ["📋 **待办任务:**"]
        for item in my_tasks:
            f = item.fields
            name = self.get_text_value(f.get("任务描述"))
            msg.append(f"- [{f.get('状态','待办')}] {name} ({f.get('四象限','P1')})")
        return "\n".join(msg)

    def handle_mark_done(self, open_id, keyword):
        req = SearchAppTableRecordRequest.builder().app_token(self.app_token).table_id(self.table_id).request_body(SearchAppTableRecordRequestBody.builder().build()).build()
        resp = self.client.bitable.v1.app_table_record.search(req)
        if not resp.success(): return "❌ 查找失败"
        
        target = None
        for item in resp.data.items or []:
            f = item.fields
            name = self.get_text_value(f.get("任务描述"))
            if keyword in name and f.get("状态") != "已完成" and any(o.get("id")==open_id for o in f.get("负责人",[])):
                target = item
                break
        
        if not target: return f"🔍 未找到 '{keyword}'"
        
        up_req = UpdateAppTableRecordRequest.builder().app_token(self.app_token).table_id(self.table_id).record_id(target.record_id).request_body(AppTableRecord.builder().fields({"状态": "已完成"}).build()).build()
        if self.client.bitable.v1.app_table_record.update(up_req).success():
            return f"✅ 已完成: {self.get_text_value(target.fields.get('任务描述'))}"
        return "❌ 更新失败"

    def create_native_task(self, task_name, due_ts, owner_ids):
        # 获取Token
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        t_resp = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret})
        token = t_resp.json().get("tenant_access_token")
        
        url_task = "https://open.feishu.cn/open-apis/task/v2/tasks"
        payload = {
            "summary": task_name, 
            "members": [{"id": o, "type": "user"} for o in owner_ids]
        }
        if due_ts: payload["due"] = {"time": str(due_ts)}
        
        try:
            r = requests.post(url_task, headers={"Authorization": f"Bearer {token}"}, json=payload)
            if r.status_code == 200 and r.json().get("code")==0: return "(原生任务✅)"
        except: pass
        return "(原生任务❌)"

    def handle_create(self, task_name, quadrant, due_ts, owner_ids, create_native=False):
        fields = {"任务描述": task_name, "四象限": quadrant, "状态": "待办", "负责人": [{"id": o} for o in owner_ids]}
        if due_ts: fields["截止日期"] = due_ts
        
        req = CreateAppTableRecordRequest.builder().app_token(self.app_token).table_id(self.table_id).request_body(AppTableRecord.builder().fields(fields).build()).build()
        resp = self.client.bitable.v1.app_table_record.create(req)
        
        msg = f"✅ 任务已建\n📌 {task_name}\n🎯 {quadrant}"
        if create_native:
            msg += f"\n{self.create_native_task(task_name, due_ts, owner_ids)}"
        return msg
