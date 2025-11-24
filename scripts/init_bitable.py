import requests
import json
import time

# 读取配置
with open("config.json", "r") as f:
    config = json.load(f)

APP_ID = config["APP_ID"]
APP_SECRET = config["APP_SECRET"]

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

def create_bitable(token):
    # 1. 创建多维表格 App
    # 注意：需要先在某个文件夹下创建，或者直接创建在根目录。
    # API: Create App (bitable)
    # 这里的 folder_token 留空通常会创建在“我的空间”根目录，或者需要指定一个具体的 folder_token
    # 为了简单，我们尝试直接创建一个 bitable 文件
    
    print("正在创建多维表格文件...")
    url = "https://open.feishu.cn/open-apis/drive/v1/files"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    # "type": "bitable" 创建多维表格
    payload = {
        "name": "项目任务管理(Bot)",
        "type": "bitable" 
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"❌ 创建表格文件失败: {response.text}")
        return None, None

    data = response.json().get("data", {})
    app_token = data.get("token") # 这是文件的 token，也是 bitable 的 app_token
    url = data.get("url")
    print(f"✅ 表格创建成功！\n链接: {url}\nApp Token: {app_token}")
    return app_token, url

def setup_table_fields(token, app_token):
    # 1. 获取默认的数据表 (Table) ID
    # 一个 Bitable app 下面可能有多个 table (工作表)
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
    print(f"默认工作表 ID: {table_id}")

    # 2. 改造字段 (Fields)
    # 我们无法直接“重命名”默认字段而不清楚它的ID，通常默认第一列是“多行文本”
    # 策略：获取现有字段 -> 找到文本列改名为“任务名称” -> 新增其他列
    
    url_fields = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
    resp_fields = requests.get(url_fields, headers=headers)
    fields = resp_fields.json().get("data", {}).get("items", [])
    
    # --- 2.1 修改/确认第一列 ---
    # 找到第一个 Text 类型的字段，改名为 "任务名称"
    print("正在配置列...")
    
    text_field = next((f for f in fields if f["ui_type"] == "Text"), None)
    if text_field:
        # 更新字段名
        url_update = f"{url_fields}/{text_field['field_id']}"
        requests.put(url_update, headers=headers, json={"field_name": "任务名称"})
        print("  - ✅ '任务名称' 列配置完成")
    else:
        # 如果没有，就新建
        requests.post(url_fields, headers=headers, json={"field_name": "任务名称", "type": 1})

    # --- 2.2 新增 "负责人" (User) ---
    # type 11 = User
    requests.post(url_fields, headers=headers, json={
        "field_name": "负责人",
        "type": 11,
        "property": {"multiple": True}
    })
    print("  - ✅ '负责人' 列创建完成")

    # --- 2.3 新增 "优先级" (Single Select) ---
    # type 3 = Single Select
    requests.post(url_fields, headers=headers, json={
        "field_name": "优先级",
        "type": 3,
        "property": {
            "options": [
                {"name": "高", "color": 0}, # 红色
                {"name": "中", "color": 1}, # 橙色
                {"name": "低", "color": 2}  # 黄色/绿色
            ]
        }
    })
    print("  - ✅ '优先级' 列创建完成")

    # --- 2.4 新增 "截止日期" (Date) ---
    # type 5 = Date
    requests.post(url_fields, headers=headers, json={
        "field_name": "截止日期",
        "type": 5
    })
    print("  - ✅ '截止日期' 列创建完成")

    print("\n🎉 所有初始化工作完成！")

if __name__ == "__main__":
    token = get_tenant_access_token()
    if token:
        app_token, url = create_bitable(token)
        if app_token:
            setup_table_fields(token, app_token)
