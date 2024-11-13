import os
import json
import time
import requests
import traceback
from config import Config

from server.base import BaseServer


class LLaMAServer(BaseServer):
    SERVER_KEY = "llama"
    def __init__(self) -> None:
        super().__init__()
        self.config = Config()
        self.url = os.environ.get("LLaMA_SERVER_URL")

        self.headers = {
            "Content-Type":"application/json",
            "Authorization":f"Bearer {os.environ.get('LLaMA_API_KEY')}"
        }

    def get_task(self):
        data = self.r.rpop(self.config.REDIS_LLAMA_TASK_KEY)
        if not data: return False, None
        return True, json.loads(data)
    
    def on_error(self, e: Exception, data):
        self.config.log_error(self.SERVER_KEY, "".join(traceback.format_exception(e)))
        raise e

        
    def execute(self, data:dict):
        task_id = data.get("task_id")
        post_data = data.copy()
        post_data.pop("task_id")

        post_data["messages"] = json.dumps(post_data["messages"])
        post_data["model"] = "llama"
        post_data["password"] = "BioMedAgent"
        response = requests.post(f"{self.url}/openai", json=post_data,headers={"Content-Type": "application/json", "charset": "utf-8"})
        data = response.json()
        print(data)
        uid = data["uid"]
        while True:
            response = requests.get(f"{self.url}/openai/{uid}")
            print(response.text)
            if response.status_code != 200:
                time.sleep(1)
                continue
            data = response.json()
            if not data["result"]:
                time.sleep(1)
                continue
            text = data["text"]
            self.r.hset(self.config.REDIS_LLAMA_RESULT_KEY, task_id, json.dumps({
                "response": text
            }))
            break