import requests
import json
import time

# 读取配置
with open("config.json", "r") as f:
    config = json.load(f)

APP_ID = config["APP_ID"]
APP_SECRET = config["APP_SECRET"]
BITABLE_APP_TOKEN = "DR8mbUoyUazoQ9sk0VTcB5sLnkh" # 用户提供

def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json().get("tenant_access_token")
    else:
        print(f"❌ 获取 Token 失败: {response.text}")
        return None

def setup_table_fields(token, app_token):
    # 1. 获取默认的数据表 (Table) ID
    print("正在获取默认数据表...")
    url_list_tables = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables"
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(url_list_tables, headers=headers)
    if resp.status_code != 200:
        print(f"❌ 获取工作表失败: {resp.text}")
        return

    tables = resp.json().get("data", {}).get("items", [])
    if not tables:
        print("❌ 没有找到默认工作表")
        return
    
    table_id = tables[0]["table_id"]
    print(f"✅ 找到工作表 ID: {table_id}")

    # 2. 改造字段 (Fields)
    url_fields = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
    resp_fields = requests.get(url_fields, headers=headers)
    fields = resp_fields.json().get("data", {}).get("items", [])
    
    # 打印现有字段方便调试
    print(f"当前字段数量: {len(fields)}")

    # --- 2.1 修改/确认第一列 (文本) ---
    text_field = next((f for f in fields if f["ui_type"] == "Text"), None)
    if text_field:
        url_update = f"{url_fields}/{text_field['field_id']}"
        requests.put(url_update, headers=headers, json={"field_name": "任务名称"})
        print("  - ✅ '任务名称' 列配置完成 (重命名)")
    else:
        requests.post(url_fields, headers=headers, json={"field_name": "任务名称", "type": 1})
        print("  - ✅ '任务名称' 列配置完成 (新建)")

    # --- 2.2 新增 "负责人" (User) ---
    # 先检查是否已存在
    if not any(f["field_name"] == "负责人" for f in fields):
        requests.post(url_fields, headers=headers, json={
            "field_name": "负责人",
            "type": 11,
            "property": {"multiple": True}
        })
        print("  - ✅ '负责人' 列创建完成")
    else:
        print("  - ℹ️ '负责人' 列已存在，跳过")

    # --- 2.3 新增 "优先级" (Single Select) ---
    if not any(f["field_name"] == "优先级" for f in fields):
        requests.post(url_fields, headers=headers, json={
            "field_name": "优先级",
            "type": 3,
            "property": {
                "options": [
                    {"name": "高", "color": 0},
                    {"name": "中", "color": 1},
                    {"name": "低", "color": 2}
                ]
            }
        })
        print("  - ✅ '优先级' 列创建完成")
    else:
        print("  - ℹ️ '优先级' 列已存在，跳过")

    # --- 2.4 新增 "截止日期" (Date) ---
    if not any(f["field_name"] == "截止日期" for f in fields):
        requests.post(url_fields, headers=headers, json={
            "field_name": "截止日期",
            "type": 5
        })
        print("  - ✅ '截止日期' 列创建完成")
    else:
        print("  - ℹ️ '截止日期' 列已存在，跳过")

    print("\n🎉 表格结构配置完成！")

if __name__ == "__main__":
    token = get_tenant_access_token()
    if token:
        setup_table_fields(token, BITABLE_APP_TOKEN)
