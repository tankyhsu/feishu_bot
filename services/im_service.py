import json
import logging
from lark_oapi.api.im.v1.model import (
    ReplyMessageRequest, 
    ReplyMessageRequestBody,
    UpdateMessageRequest, 
    UpdateMessageRequestBody
)

class IMService:
    def __init__(self, client):
        self.client = client

    def reply(self, msg_id, text):
        """Reply to a message"""
        req = ReplyMessageRequest.builder() \
            .message_id(msg_id) \
            .request_body(ReplyMessageRequestBody.builder() \
                .content(json.dumps({"text": text})) \
                .msg_type("text") \
                .build()) \
            .build()
            
        resp = self.client.im.v1.message.reply(req)
        if resp.success():
            return resp.data.message_id
        else:
            logging.error(f"Failed to reply message: {resp.code} - {resp.msg}")
            return None

    def update(self, msg_id, text):
        """Update a message"""
        req = UpdateMessageRequest.builder() \
            .message_id(msg_id) \
            .request_body(UpdateMessageRequestBody.builder() \
                .content(json.dumps({"text": text})) \
                .msg_type("text") \
                .build()) \
            .build()
            
        resp = self.client.im.v1.message.update(req)
        if not resp.success():
            logging.error(f"Failed to update message {msg_id}: {resp.code} - {resp.msg}")
            return False
        return True
