import json
import redis
import time

from config import Config
from utils import generate_task_id, gprint, rprint

conn = redis.StrictRedis(decode_responses=True)

def push_code(code:str, test_func_name:str, config:Config, ensure_active=True, official=False):
    task_id = generate_task_id()
    conn.lpush(config.REDIS_EXECUTOR_LIST_TASK_KEY, json.dumps({
        "task_id":task_id,
        "task_path":config.task_path,
        "code":code,
        "test_func_name":test_func_name,
        "ensure_active":ensure_active,
        "official":official
    }, ensure_ascii=False))
    return task_id

def get_code_output(task_id:str, config:Config):
    while True:
        result = conn.hget(config.REDIS_EXECUTOR_LIST_DATA_KEY,task_id)
        if result is not None:
            return json.loads(result)
        time.sleep(config.EXECUTOR_CODE_WAITING_TIME)