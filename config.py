import os
import redis
from datetime import datetime

def time_dir():
    now = datetime.now()
    return os.path.join(
        f"{now.year}-{now.month}",f"{now.day}"
    )

class Config:
    LLM_CALL_PASSWORD = "BioMedAgent"
    LLM_CALL_WAITING_TIME = 1
    LLM_SERVER_IP = ""

    BASE_DIR = "./"
    LOG_DIR = os.path.join(BASE_DIR,"log")
    TASK_DIR = "task"
    TOOL_DOC_DIR = "tool/doc"
    TOOL_CODE_DIR = "tool/code"

    ZIP_DIR = "zip"

    SAVE_LOG = True
    ECHO_INFO = True

    SAVE_MEMORY = False
    MEMORY_PREFIX = "v1.0.0"

    USE_MEMORY = False
    USE_FILE_APPENDIX = False

    BASE_LLM_MODEL = "gpt-4o-mini"
    SUPER_LLM_MODEL = "gpt-4o-mini"

    HIGHSCORE_TOOL_THRESHOLD = 5
    WORKFLOW_USED_TOOL_THRESHOLD = 5

    EXECUTOR_CODE_WAITING_TIME = 1
    ACTION_RETRY_TIMES = 4

    #######################################
    REDIS_HOST = "localhost"
    REDIS_PORT = 6379

    REDIS_GPT_TASK_KEY = "biomedagent:gpt:task"
    REDIS_GPT_RESULT_KEY = "biomedagent:gpt:result"


    REDIS_LLAMA_TASK_KEY = "biomedagent:llama:task"
    REDIS_LLAMA_RESULT_KEY = "biomedagent:llama:result"

    REDIS_EXECUTOR_LIST_TASK_KEY = "biomedagent:executor:task"
    REDIS_EXECUTOR_LIST_DATA_KEY = "biomedagent:executor:data"

    REDIS_ACTIVE_TOOL_KEY = "biomedagent:tools:active"
    REDIS_TOOL_INFO_KEY = "biomedagent:tools:info"
    REDIS_STATUS_DATA_KEY = "biomedagent:status:data"
    REDIS_STATUS_LIST_KEY = "biomedagent:status:list"
    REDIS_PROGRESS_DATA_KEY = "biomedagent:progress_data"
    REDIS_RESULT_DATA_KEY = "biomedagent:result_data"

    REDIS_INSTANCE_INFO_KEY = "biomedagent:instance:info"
    REDIS_INSTANCE_PUBLISH_KEY = "biomedagent:instance:publish"

    REDIS_MEMORY_STORAGE_KEY = f"biomedagent:memory:{MEMORY_PREFIX}:storage"
    REDIS_MEMORY_INFO_KEY = f"biomedagent:memory:info"
    REDIS_MEMORY_TASK_KEY = f"biomedagent:memory:{MEMORY_PREFIX}:task"
    REDIS_MEMORY_RESULT_KEY = f"biomedagent:memory:{MEMORY_PREFIX}:result"
    REDIS_MEMORY_LOG = f"biomedagent:memory:{MEMORY_PREFIX}:log:"
    REDIS_MEMORY_LOG2 = f"biomedagent:memory:{MEMORY_PREFIX}:log"

    def __init__(self, task_id=None) -> None:
        self.task_id = task_id
        self.time_path = time_dir()

    def get_task(self):
        if self.task_id is None:
            raise ValueError("task id is None")
        return f"{self.task_id}"
    
    def get_redis_connect(self):
        return redis.Redis(self.REDIS_HOST,self.REDIS_PORT,decode_responses=True)
    
    @classmethod
    def set_task(cls,task_id):
        return Config(task_id)
    
    def log_error(self, item:str, message:str):
        time = datetime.now()
        with open("BioLog/error.log","a",encoding="utf8") as f:
            f.write(f"{item=}\n{time=}\n{message=}\n{'='*50}\n")


config = Config()