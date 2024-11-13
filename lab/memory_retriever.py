import json
import time
from config import Config
from utils import generate_task_id

class TestMemoryRetriever:
    def __init__(self) -> None:
        self.r = Config().get_redis_connect()
        self.config = Config()

    def match(self, item_key, query_key, total_task_id, k=2):
        k = 3
        task_id = generate_task_id()
        data = {
            "task_id":task_id,
            "item_key":item_key,
            "query_key":query_key,
            "k":k,
            "threshold":0.4
        }
        self.r.lpush(self.config.REDIS_MEMORY_TASK_KEY,json.dumps(data))
        while True:
            result = self.r.hget(self.config.REDIS_MEMORY_RESULT_KEY, task_id)
            if result is None:
                time.sleep(1)
            else:
                result = json.loads(result)
                if len(result) == 0:
                    self.config.log_error("special", "result is None")
                    return ""
                content = []
                for item in result:
                    content.append(item["value"])
                    self.r.lpush(self.config.REDIS_MEMORY_LOG2, json.dumps({
                        "item_key":item_key,
                        "current_query_key":query_key,
                        "origin_query_key":item["key"],
                        "query_value":item["value"],
                        "memory_id":item["id"],
                        "origin_question_id":item["question_id"],
                        "current_task_id":total_task_id,
                        "k":len(result),
                        "score":item["score"]
                    }))
                content = f"\n{'='*10}\n".join(content)
                response = f"""
Here's a summary of some of your experiences and memories that you can use for reference: 【\n{content}\n】You must learn from experience and memory as well as reference!
"""
                return response