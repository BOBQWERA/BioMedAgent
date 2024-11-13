import json
import bisect
from BCEmbedding import RerankerModel

from config import Config
from server.base import BaseServer


class KBRetriever(BaseServer):

    SERVER_KEY = "kbr"

    def __init__(self) -> None:
        super().__init__()
        self.config = Config()
        self.reranker_model = RerankerModel(model_name_or_path="model/bce-reranker-base_v1")

    def get_task(self):
        data = self.r.rpop(self.config.REDIS_MEMORY_TASK_POST_KEY)
        if not data: return False, None
        return True, json.loads(data)
    
    def execute(self, data:dict):
        task_id = data["task_id"]
        query_text = data["query_text"]
        query_item = data["query_item"]
        k = data.get("k", 5)
        threshold = data.get("threshold", 0.4)
        
        query_info = self.r.lrange(
            f"{self.config.REDIS_MEMORY_STORAGE_KEY}:{query_item}", 0, -1
        )

        query_list = []
        query_dict = {}

        for item in query_info:
            item = json.loads(item)
            query_list.append(item["key"])
            query_dict[item["key"]] = item["value"]

        rerank_results = self.reranker_model.rerank(query_text, query_list)
        k = min(k, bisect.bisect_left(rerank_results["rerank_scores"], -threshold, key=lambda x:-x))
        top_k_item = rerank_results["rerank_passages"][:k]

        result = []
        for item in top_k_item:
            result.append(query_dict[item])

        self.r.hset(self.config.REDIS_MEMORY_TASK_GET_KEY, task_id, json.dumps(result))
        

