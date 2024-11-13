import re
import json

from BCEmbedding import RerankerModel
from utils import gprint

from config import Config
r = Config().get_redis_connect()
class InstanceRetriever:
    def __init__(self) -> None:
        self.reranker_model = RerankerModel(model_name_or_path="model/bce-reranker-base_v1")
        self.r = Config().get_redis_connect()
        self._instance_dict = self._prepare()

    def _get_instances_info(self, instance_id:str):
        info = self.r.hget(Config.REDIS_INSTANCE_INFO_KEY, instance_id)
        if not info: raise Exception("非法instance_id")
        info:dict = json.loads(info)
        result = r.get(f"biomedagent:result:{instance_id}")
        files = None
        if result:
            batch_info = r.get(f"biomedagent:info:batch_task:{instance_id}")
            normal_info = r.get(f"biomedagent:info:normal_task:{instance_id}")
            if batch_info:
                batch_info = json.loads(batch_info)
                files = batch_info["files"]
            elif normal_info:
                normal_info = json.loads(normal_info)
                files = normal_info["files"]
        question = info.get("question")
        if not question: raise Exception("非法instance数据")
        if not files:
            files = info.get("files")
        if not files: files = re.findall("\{(.*?)\}",question)
        return question, files

    def _prepare(self):
        instance_dict = dict()
        instances = self.r.hkeys(Config.REDIS_INSTANCE_PUBLISH_KEY)
        for instance_id in instances:
            question, files = self._get_instances_info(instance_id)
            publish_info = json.loads(self.r.hget(Config.REDIS_INSTANCE_PUBLISH_KEY, instance_id))
            instance_dict[question] = {
                "question":question,
                "files":files,
                "id":instance_id,
                "type":publish_info["type"]
            }
        return instance_dict
    
    def match(self, prompt, k=5):
        self._instance_dict = self._prepare()
        if prompt == "":prompt = "我"
        instances = list(self._instance_dict.keys())
        
        rerank_results = self.reranker_model.rerank(prompt, instances)
        top_k_instances = rerank_results["rerank_passages"][:k]
        result = []
        
        for item in top_k_instances:
            result.append({
                "question":item,
                "id":self._instance_dict[item]["id"],
                "files":self._instance_dict[item]["files"],
                "type":self._instance_dict[item]["type"]
            })
        return result
        
if __name__ == "__main__":
    retriever = InstanceRetriever()
    result = retriever.match("vcf转化maf")
    print(result)
    