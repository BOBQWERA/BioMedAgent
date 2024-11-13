import os
import json
import requests
import traceback
from config import Config

from server.base import BaseServer
import warnings

from requests.exceptions import ConnectionError

class GPTResponseFormatError(Exception):
    ...

class GPTServer(BaseServer):
    SERVER_KEY = "gpt"
    def __init__(self) -> None:
        super().__init__()
        self.config = Config()
        self.url = os.environ.get('OPENAI_BAE_URL')

        self.headers = {
            "Content-Type":"application/json",
            "Authorization":f"Bearer {os.environ.get('OPENAI_API_KEY')}"
        }

    def get_task(self):
        data = self.r.rpop(self.config.REDIS_GPT_TASK_KEY)
        if not data: return False, None
        return True, json.loads(data)
    
    def on_error(self, e: Exception, data):
        self.config.log_error(self.SERVER_KEY, "".join(traceback.format_exception(e)))
        if "string_above_max_length" in "".join(traceback.format_exception(e)):
            return
        elif "context_length_exceeded" in "".join(traceback.format_exception(e)):
            return
        
        if isinstance(e, requests.exceptions.ProxyError):
            self.r.rpush(self.config.REDIS_GPT_TASK_KEY, json.dumps(data))
        elif isinstance(e, GPTResponseFormatError):
            self.r.rpush(self.config.REDIS_GPT_TASK_KEY, json.dumps(data))
        elif isinstance(e, ConnectionError):
            self.r.rpush(self.config.REDIS_GPT_TASK_KEY, json.dumps(data))

        
    def execute(self, data:dict):
        task_id = data.get("task_id")
        post_data = data.copy()
        post_data.pop("task_id")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = requests.post(self.url, headers=self.headers, json=post_data, verify=False).json()
        if "choices" not in response:
            raise GPTResponseFormatError(json.dumps(response))
        content = response["choices"][0]["message"]["content"]
        self.r.hset(self.config.REDIS_GPT_RESULT_KEY, task_id, json.dumps({
            "response": content
        }))

if __name__ == "__main__":
    server = GPTServer()
    server.r.lpush(server.config.REDIS_GPT_TASK_KEY, json.dumps({
        "messages":[{
            "role":"user",
            "content":"hi"
        }],
        "model":"gpt-3.5-turbo",
        "temperature":0.5
    }))

    server.run()