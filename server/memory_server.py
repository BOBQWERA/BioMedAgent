import json
import bisect
from config import Config
from BCEmbedding import RerankerModel
from server.base import BaseServer

class MemoryServer(BaseServer):
    SERVER_KEY = "memory"

    def __init__(self) -> None:
        super().__init__()
        self.config = Config()
        self.reranker_model = RerankerModel(model_name_or_path="model/bce-reranker-base_v1")

    def get_task(self):
        data = self.r.rpop(self.config.REDIS_MEMORY_TASK_KEY)
        if not data: return False, None
        return True, json.loads(data)
    
    def execute(self, data:dict):
        task_id = data.get("task_id")
        item_key = data.get("item_key")
        query_key = data.get("query_key")
        k = data.get("k")
        threshold = data.get("threshold", 0.4)

        memory = self.r.lrange(f"{self.config.REDIS_MEMORY_STORAGE_KEY}:{item_key}",0,-1)
        info = {}
        query_list = []
        for item in memory:
            item = json.loads(item)
            if item["value"] is None:
                self.config.log_error(self.SERVER_KEY, json.dumps(data,indent=4))
                continue
            info[item["key"]] = {
                "value":item["value"],
                "id":item["id"],
                "question_id":item["question_id"],
                "key":item["key"],
            }
            query_list.append(item["key"])
        try:
            rerank_results = self.reranker_model.rerank(query_key, query_list)
        except AssertionError as e:
            self.r.hset(self.config.REDIS_MEMORY_RESULT_KEY, task_id, json.dumps([]))
            return
        k = min(k, bisect.bisect_left(rerank_results["rerank_scores"], -threshold, key=lambda x:-x))
        top_k_instances = rerank_results["rerank_passages"][:k]
        result = []
        for item,score in zip(top_k_instances,rerank_results["rerank_scores"]):
            info[item]["score"] = score
            result.append(info[item])
        self.r.hset(self.config.REDIS_MEMORY_RESULT_KEY, task_id, json.dumps(result))