import os
import json
import time
import redis
from typing import Any


from config import Config
from utils import yprint,generate_task_id

from scripts.prompt import file_appendix_prompt
from lab.file_reader import file_reader


class Status:
    def __init__(self, task_id:str, config:Config, update) -> None:
        self.data = {}
        self.task_id = task_id
        self.config = config
        self.update = update

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name not in ["data","taskid","config","update"]:
            self.data[name] = value

    def __getattr__(self, name: str):
        try:
            self.data[name]
        except:
            return self.__getattr__(name)

    def get(self, name):
        return self.data.get(name)

    def show(self):
        yprint("="*30)
        print(self.data)
        yprint("="*30)

    def save(self, output_path='output.json'):
        with open(output_path,"w",encoding="utf8") as f:
            json.dump(self.data,f)

    def status_update(self, stage:str):
        if not self.update: return
        now = int(time.time())
        self.upload_status = {
            "stage":stage,
            "time":now
        }
        self.config.get_redis_connect().lpush(
            f"{self.config.REDIS_STATUS_LIST_KEY}:{self.task_id}",json.dumps({
                "uid":generate_task_id(),
                "stage":stage
            })
        )
        self.config.get_redis_connect().hset(
            self.config.REDIS_STATUS_DATA_KEY, self.task_id, json.dumps(self.data)
        )

class Task:
    def __init__(self, info:dict, config:Config, update=False, official=False) -> None:
        """
        info example:
        {
            "question":"this is a question",
            "files":[
                {
                    "name":"demo1",
                    "path":"/mnt/data/example/demo1"
                },
                {
                    "name":"demo2",
                    "path":"/mnt/data/example/demo2"
                }
            ]
        }
        """
        self.official = official
        

        question = info.get("question") 
        files = info.get("files")

        self.question = question

        self.files = files
        self.config = config

        self.status = Status(self.config.get_task(), config, update)
        self.tool_manager = ToolManager(config)

        self.prepare()

    def prepare(self):
        self.raw_question = self.question
        task_id = self.config.get_task()
        task_path = os.path.join(
            f"{self.config.TASK_DIR}",self.config.time_path,task_id
        )

        self.config.task_path = task_path
        self.status.task_path = task_path
        self.status.raw_question = self.raw_question
        self.status.backtrack = []

        self.status.files = self.file_list

        self.file_appendix = ""

        if self.config.USE_FILE_APPENDIX:
            for f in self.files:
                ok, info = file_reader(f["name"],f["path"])
                if not ok:continue
                self.file_appendix += file_appendix_prompt.replace(
                    "{type}",info["type"]
                ).replace(
                    "{name}",f["name"]
                ).replace(
                    "{content}", info["content"]
                )
            with open("data/use_file_appendix.txt","w") as f:
                f.write(self.file_appendix)
            

        if not os.path.exists(task_path):
            os.makedirs(task_path)

        for file in self.files:
            print(file['path'])
            if not os.path.exists(file['path']):
                raise FileNotFoundError(f"no file:{file['path']=}")
            os.system(f"cp {file['path']} {task_path}")
        #?###########################
        self.status.tools = {}
        tools = os.listdir(self.config.TOOL_DOC_DIR)
        # self.status.tools = {}
        for tool in tools:
            if tool.startswith("."):
                continue
            with open(os.path.join(self.config.TOOL_DOC_DIR,tool),"r",encoding="utf8") as f:
                document = f.read()
            self.status.tools[tool] = {
                "document":document
            }
        self.status.rescored = False
        self.status.code = {}

    def backtrack_update(self):
        self.status.backtrack.append({
            "workflow" : self.status.workflow,
            "tool_used": self.status.tool_used,
            "workflow_stages": self.status.workflow_stages,
            "resource_pool":self.status.resource_pool,
            "code_result":self.status.code_result,
            "code":self.status.code
        })
        self.status.tool_used = {}
        self.status.workflow_stages = []
        self.status.resource_pool = []
        self.status.code_result = {}
        self.status.code = {}

    @property
    def file_list(self):
        result = []
        for file in self.files:
            result.append(file['name'])
        return result
    
    @classmethod
    def fake_task(cls, config):
        fake_info = {"question":"","files":[]}
        return Task(
            fake_info, config
        )

    
class ToolManager:
    def __init__(self, config:Config) -> None:
        self.config = config
        self.r = config.get_redis_connect()

    def get_tool_list(self, ensure_active = True):
        if ensure_active:
            tools = self.r.hkeys(self.config.REDIS_ACTIVE_TOOL_KEY)
            return tools
        else:
            tool_ids = self.r.hkeys(self.config.REDIS_TOOL_INFO_KEY)
            return tool_ids
        
    
    def get_tool_info(self, tool_name):
        tool_id = self.r.hget(self.config.REDIS_ACTIVE_TOOL_KEY, tool_name)
        if not tool_id:
            return False, None
        tool_info = self.r.hget(self.config.REDIS_TOOL_INFO_KEY, tool_id)
        if not tool_info:
            return False, None
        return True, json.loads(tool_info)
    
    def get_tool_info_by_id(self, tool_id):
        tool_info = self.r.hget(self.config.REDIS_TOOL_INFO_KEY, tool_id)
        if not tool_info:
            return False, None
        return True, json.loads(tool_info)
    
    def get_tool_code(self, tool_name):
        ok, info = self.get_tool_info(tool_name)
        return info["tool_code"]
    
    def get_tool_doc(self, tool_name):
        ok, info = self.get_tool_info(tool_name)
        return info["tool_doc"]
    
    def get_tool_code_by_id(self, tool_id):
        ok, info = self.get_tool_info_by_id(tool_id)
        return info["tool_code"]
    
    def get_tool_doc_by_id(self, tool_id):
        ok, info = self.get_tool_info_by_id(tool_id)
        return info["tool_doc"]
    
    def get_tool_name_by_id(self, tool_id):
        ok, info = self.get_tool_info_by_id(tool_id)
        return info["tool_name"]
    
if __name__ == "__main__":
    config = Config()

    tool_manager = ToolManager(config)
    tools = tool_manager.get_tool_list()

    print(tools)
    print(type(tools))