import json
import logging
import lark_oapi as lark
from lark_oapi.api.bitable.v1.model import (
    SearchAppTableRecordRequest,
    SearchAppTableRecordRequestBody
)

# 配置日志
logging.basicConfig(level=logging.INFO)

# 读取配置
with open("config.json", "r") as f:
    config = json.load(f)

APP_ID = config["APP_ID"]
APP_SECRET = config["APP_SECRET"]
BITABLE_APP_TOKEN = config["BITABLE_APP_TOKEN"]
TABLE_ID = config["TABLE_ID"]

# 初始化客户端
client = lark.Client.builder() \
    .app_id(APP_ID) \
    .app_secret(APP_SECRET) \
    .log_level(lark.LogLevel.INFO) \
    .build()

def debug_query():
    print("🔍 开始诊断查询逻辑...")
    
    # 1. 全量拉取
    req = SearchAppTableRecordRequest.builder() \
        .app_token(BITABLE_APP_TOKEN) \
        .table_id(TABLE_ID) \
        .request_body(SearchAppTableRecordRequestBody.builder().build()) \
        .build()

    resp = client.bitable.v1.app_table_record.search(req)
    
    if not resp.success():
        print(f"❌ API 请求失败: {resp.code} - {resp.msg}")
        return

    items = resp.data.items or []
    print(f"📊 共拉取到 {len(items)} 条记录。")
    
    if not items:
        print("⚠️ 表格是空的！请先创建一个任务。")
        return

    # 2. 打印前 3 条数据的详细结构
    print("\n--- 前 3 条记录详情 ---")
    for i, item in enumerate(items[:3]):
        print(f"\n[Record {i+1}] Record ID: {item.record_id}")
        fields = item.fields
        print(f"  - 任务描述: {fields.get('任务描述')}")
        print(f"  - 状态: {fields.get('状态')}")
        
        owners = fields.get("负责人")
        print(f"  - 负责人 (Raw): {owners}")
        
        if owners:
            for o in owners:
                print(f"    -> ID: {o.get('id')}, Name: {o.get('name')}")
        else:
            print("    -> (无负责人)")

    print("\n--- 诊断建议 ---")
    print("1. 检查 '状态' 是否真的是 '待办' (注意空格)。")
    print("2. 检查 '负责人' 里的 ID 是否存在。")
    print("3. 如果你看到 ID，请把这个 ID 和你的 OpenID 对比。")

if __name__ == "__main__":
    debug_query()
