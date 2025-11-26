import logging
import datetime

class MinutesHandler:
    def __init__(self, minutes_service, doc_service, im_service):
        self.mm = minutes_service
        self.dm = doc_service
        self.im = im_service

    def handle(self, msg_id, text, sender_id):
        """Handle minutes processing workflow"""
        
        # 1. Check if it's a minutes link
        minutes_token = self.mm.extract_minutes_token(text)
        if not minutes_token:
            return False

        # 2. Send initial response
        initial_reply_id = self.im.reply(msg_id, "🎧 收到会议录音，正在处理中...")
        
        final_response_text = ""
        
        try:
            # 3. Fetch subtitle
            subtitle = self.mm.fetch_subtitle(minutes_token)
            if not subtitle:
                final_response_text = "❌ 无法读取妙记。请确认已授予机器人权限并分享链接。"
            else:
                # 4. Summarize
                summary_result = self.mm.summarize(subtitle)
                
                if isinstance(summary_result, dict):
                    summary_content = summary_result.get("content", "")
                    summary_title = summary_result.get("title", "会议纪要")
                else:
                    summary_content = str(summary_result)
                    summary_title = "会议纪要"

                final_response_text = summary_content 

                # 5. Create Doc
                try:
                    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    doc_title = f"{summary_title} - {today_str}"
                    
                    doc_id = self.dm.create_document(doc_title)
                    if doc_id:
                        self.dm.add_content(doc_id, summary_content)
                        doc_url = f"https://feishu.cn/docx/{doc_id}"
                        
                        final_response_text = f"✅ 会议纪要已生成云文档: [{doc_title}]({doc_url})"
                        
                        # 6. Transfer Ownership
                        if self.dm.transfer_ownership(doc_id, sender_id):
                            final_response_text += "\n✅ 所有权已转移给你。"
                        else:
                            final_response_text += "\n⚠️ 所有权转移失败，请检查机器人是否具备足够权限（如：云文档所有者转移）。"
                    else:
                        final_response_text += "\n\n❌ 文档创建失败，请检查权限。"
                except Exception as e:
                    final_response_text += f"\n\n❌ 保存文档异常: {e}"

        except Exception as e:
            final_response_text = f"❌ 处理妙记时发生异常: {e}"
        
        # 7. Update message
        if initial_reply_id:
            self.im.update(initial_reply_id, final_response_text)
        else:
            self.im.reply(msg_id, final_response_text)
            
        return True
