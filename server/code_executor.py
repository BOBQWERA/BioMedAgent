import os
import json

from server.base import BaseServer
from config import Config
from component import ToolManager

from utils import rprint,gprint

class CodeExecutor(BaseServer):
    SERVER_KEY = "code"
    def __init__(self) -> None:
        super().__init__()
        self.config = Config()
        self.tool_manager = ToolManager(self.config)

    def get_task(self):
        result = self.r.rpop(self.config.REDIS_EXECUTOR_LIST_TASK_KEY)
        if result is None:
            return False, None
        return True, json.loads(result)
    
    def add_chdir_code(self, code, task_path):
        return f"""
import os
os.chdir("{task_path}")

{code}
"""
    
    def add_official_tools_code(self, code):
        tools_code = ""
        tools = os.listdir(self.config.TOOL_CODE_DIR)
        for tool in tools:
            if tool.startswith("."): continue
            if tool not in code: continue
            with open(os.path.join(self.config.TOOL_CODE_DIR,tool),"r",encoding='utf8') as f:
                tools_code += f"\n{f.read()}\n"
        return f"""
{tools_code}

{code}
"""
    
    def add_tools_code(self, code, ensure_active):
        tools_code = ""
        tools = self.tool_manager.get_tool_list(ensure_active)
        for tool in tools:
            if ensure_active:
                tool_name = tool
            else:
                tool_name = self.tool_manager.get_tool_name_by_id(tool)
            if tool_name in code:
                if ensure_active:
                    tool_code = self.tool_manager.get_tool_code(tool_name)
                else:
                    tool_code = self.tool_manager.get_tool_code_by_id(tool)
                tools_code+=f"\n{tool_code}\n"
        return f"""
{tools_code}

{code}
"""
    
    def execute(self, data):
        task_id = data.get("task_id")
        code = data.get("code")
        test_func_name = data.get("test_func_name")
        ensure_active = data.get("ensure_active")
        task_path = data.get("task_path")
        official = data.get("official")

        code = self.add_chdir_code(code, task_path)
        
        if True:
            code = self.add_official_tools_code(code)
        if False: #TODO
            code = self.add_tools_code(code, ensure_active)



        os.chdir(task_path)
        namespace = {test_func_name:None}
        excepted = False
        gprint("start task")
        try:
            exec(code,namespace)
            test_func = namespace[test_func_name]
            result,data = test_func()
            json.dumps(data)
        except TypeError as e:
            excepted = True
            result, data = False,repr(e)
            if "not JSON serializable" in data:
                data = "The return value of a function should be a base type and not a non-jsonizable object."
        except SyntaxError as e:
            excepted = True
            result, data = False,repr(e)
            data += "\nPlease note, double check the code for syntax issues, variable names, indentation, etc."
        except ModuleNotFoundError as e:
            excepted = True
            result, data = False,repr(e)
            data += "\nImporting hypothetical third-party libraries on your own is prohibited, while the given tool code does not need to be imported!"
        except Exception as e:
            excepted = True
            result, data = False,repr(e)
        rprint("finish task")
        output = {
            "excepted":excepted,
            "result":result,
            "data":data
        }
        self.r.hset(
            self.config.REDIS_EXECUTOR_LIST_DATA_KEY,
            task_id,
            json.dumps(output,ensure_ascii=False)
        )