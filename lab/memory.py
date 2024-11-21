import json
import asyncio

from scripts.component import Task
from agent import BaseAgent, ResponseHandler, ResponseChecker

from config import Config

from scripts.prompt import *

from utils import knowledge_base, generate_task_id, extract_function

class TestMemoryToolAgent(BaseAgent):
    system = memory_tool_system
    actions_template = {
        "initial":{
            "prompt":memory_tool_prompt,
            "keyword":[
                "question", "workflow", "tool_name", "tool_doc"
            ]
        }
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self.model = self.config.SUPER_LLM_MODEL

    @ResponseHandler.xml_tag_content_handler("SUGGESTION", multi=True)
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("SUGGESTION"), multi=True)
    async def tool_memory(self, tool_name:str, tool_doc:str):
        question = self.task.status.get("question")
        workflow = self.task.status.get("workflow")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "question":question,
            "workflow":workflow,
            "tool_name":tool_name,
            "tool_doc":tool_doc,
        })
        response = await session.chat(prompt)
        return response
    
    async def tools_memory(self):
        tool_used = self.task.status.tool_used
        tools = self.task.status.tools
        tasks = []
        result = []
        for tool in tool_used:
            tool_name = tool
            tool_doc = tool_used[tool]["documentation"]
            tasks.append({
                "tool":tool,
                "task":asyncio.create_task(self.tool_memory(tool_name, tool_doc))
            })
        for task in tasks:
            response = await task["task"]
            result.append({
                "tool": task["tool"],
                "score":tools[task["tool"]]["re_score"],
                "suggestion": response
            })
        return result

    def memory(self, question_id, task_id):
        exps = asyncio.run(self.tools_memory())
        raw_question = self.task.status.get("raw_question")
        for item in exps:
            knowledge_base(
                item["tool"], 
                raw_question, 
                f"""
score: [{item["score"]}]
suggestion: [{item["suggestion"]}]
""",
                question_id,
                task_id
)
            
            
class TestMemoryWorkflowAgent(BaseAgent):
    system = memory_workflow_system
    actions_template = {
        "initial":{
            "prompt":memory_workflow_system,
            "keyword":[
                "question", "workflow"
            ]
        }
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self.model = self.config.SUPER_LLM_MODEL

    @ResponseHandler.xml_tag_content_handler("SUGGESTION")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("SUGGESTION"))
    def workflow_memory(self):
        question = self.task.status.get("question")
        workflow = self.task.status.get("workflow")
        
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "question":question,
            "workflow":workflow
        })
        response = asyncio.run(session.chat(prompt))
        return response
    
    def memory(self, question_id, task_id):
        raw_question = self.task.status.get("raw_question")
        # suggestion = self.workflow_memory()
        knowledge_base(
            "workflow", 
            raw_question, 
            f"""
Refer workflow: [{self.task.status.get("workflow")}]
""",
            question_id,
            task_id
)


class TestMemoryCodingAgent(BaseAgent):
    def __init__(self, task: Task) -> None:
        super().__init__(task)

    def memory(self, question_id, task_id):
        codes = self.task.status.get("code_result")["total_result"]["code_info"]
        for index,code in enumerate(codes):
            knowledge_base(
                "action",
                code["task"],
                extract_function(code["code"],f"action{index}"),
                question_id,
                task_id
            )
            knowledge_base(
                "test",
                code["task"],
                extract_function(code["code"],f"test{index}"),
                question_id,
                task_id
            )



class MemoryLab:
    def __init__(self, ref_task_id=None) -> None:
        self.ref_task_id = ref_task_id
        self.r = Config().get_redis_connect()
        

    def _get_data(self):
        
        data = self.r.get(f"biomedagent:result:{self.ref_task_id}")
        return json.loads(data)
    
    def save_data(self, path:str):
        with open(path, "w", encoding="utf8") as f:
            json.dump(self.test_data, f, indent=4)
    
    def test_tool_memory(self):
        question_data = json.loads(self.r.get(f'biomedagent:info:batch_task:{self.ref_task_id}'))
        question_id = question_data["id"]
        self.test_data = self._get_data()
        config = Config.set_task(generate_task_id())
        config.ECHO_INFO = False
        config.SAVE_LOG = False
        config.SUPER_LLM_MODEL = "gpt-4o"
        task = Task.fake_task(config)
        task.status.data = self.test_data
        task.status.tools = self.test_data["tools"]
        tool_memory = TestMemoryToolAgent(task)
        tool_memory.memory(question_id,  self.ref_task_id)
        workflow_memory = TestMemoryWorkflowAgent(task)
        workflow_memory.memory(question_id,  self.ref_task_id)
        code_memory = TestMemoryCodingAgent(task)
        code_memory.memory(question_id,  self.ref_task_id)


if __name__ == "__main__":
    lab = MemoryLab()
    lab.save_data("test_data.json")
    lab.test_tool_memory()
        