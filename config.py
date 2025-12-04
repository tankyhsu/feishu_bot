import json
import os

class Config:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.data = self._load_config()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            # Try looking in parent directory if not found (common in dev)
            if os.path.exists(os.path.join("..", self.config_path)):
                self.config_path = os.path.join("..", self.config_path)
            else:
                raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, "r") as f:
            return json.load(f)

    @property
    def APP_ID(self):
        return self.data.get("APP_ID")

    @property
    def APP_SECRET(self):
        return self.data.get("APP_SECRET")

    @property
    def BITABLE_APP_TOKEN(self):
        return self.data.get("BITABLE_APP_TOKEN")

    @property
    def TABLE_ID(self):
        return self.data.get("TABLE_ID")

    @property
    def LLM_API_KEY(self):
        return self.data.get("LLM_API_KEY")

    @property
    def LLM_BASE_URL(self):
        return self.data.get("LLM_BASE_URL", "https://api.deepseek.com")

    @property
    def LLM_MODEL(self):
        return self.data.get("LLM_MODEL", "deepseek-chat")

    @property
    def FEEDS(self):
        return self.data.get("FEEDS", [])

    @property
    def DAILY_PUSH_CHAT_ID(self):
        return self.data.get("DAILY_PUSH_CHAT_ID")
