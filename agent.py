import asyncio
import json
import re

from chat import ChatSession
from component import Task
from config import Config
from executor import push_code, get_code_output
from prompt import *
from utils import rprint, gprint, get_action_code

from lab.memory_retriever import TestMemoryRetriever


memory_retriever = TestMemoryRetriever()

class BaseAgent:
    system = "system prompt"

    actions_template = {
        "initial":{
            "prompt":"initial prompt is {{prompt}}",
            "keywords":["prompt",]
        },
        "someone":{
            "prompt":"{{value}} is good",
            "keywords":["value",]
        }
    }

    def __init__(self, task:Task) -> None:
        self.task = task
        self.config = task.config
        self.model = self.config.BASE_LLM_MODEL
        self.temperature = 0.2

    def format_template(self, action="initial", data=None, templates=None):
        if data is None:
            data = {}
        """
        data:
        {
            "prompt":"a prompt",
            "value":"some value"
        }
        """
        if templates is None:
            templates = self.actions_template
        template: str = templates.get(action)["prompt"]
        for item in data:
            template = template.replace("{"+item+"}", data[item])
        return template
    
    def create_chatsession(self, system=None):
        if system is None: system = self.system
        session = ChatSession(self.model, self.temperature, self.config)
        session.set_system(system)
        return session
    
    @staticmethod
    def status_update(key):
        def updater_decorator(func):
            def updater(self:BaseAgent, *args, **kw):
                response = func(self, *args, **kw)
                self.task.status.__setattr__(key, response)
                return response
            return updater
        return updater_decorator

    @staticmethod
    def retry(check_function=(lambda _:True),max_retry_times = 3, multi=False):
        def retry_decorator(func):
            def inner(*args, **kw):
                response = func(*args, **kw)
                retry_times = 1
                while retry_times < max_retry_times:
                    retry_times += 1
                    if not check_function(response):
                        response = func(*args, **kw)
                    else:
                        break
                else:
                    raise ValueError
                return response
            async def async_inner(*args, **kw):
                response = await func(*args, **kw)
                retry_times = 1
                while retry_times < max_retry_times:
                    retry_times += 1
                    if not check_function(response):
                        response = await func(*args, **kw)
                    else:
                        break
                else:
                    raise ValueError
                return response
            if multi:
                return async_inner
            return inner
        return retry_decorator
    

class ResponseHandler:
    @staticmethod
    def get_xml_tag_content(text,tag_name) -> str:
        results = re.findall(f'<{tag_name}>(.*?)</{tag_name}>', text, re.S)
        return results[0]
    
    @staticmethod
    def get_xml_tag_list_content(text,tag_name) -> str:
        results = re.findall(f'<{tag_name}>(.*?)</{tag_name}>', text, re.S)
        return results
    
    @staticmethod
    def assert_xml_tag_equal_handler(tag_name, equal_text, upper=True):
        def handler_decorator(func):
            def handler(*args, **kw):
                response = func(*args, **kw)
                content = ResponseHandler.get_xml_tag_content(response, tag_name)
                if upper: content = content.upper()
                return content == equal_text
            return handler
        return handler_decorator
    
    @staticmethod
    def chain_handler(chain_design_function):
        def chain_decorator(func):
            def handler(self:BaseAgent, *args, **kw):
                func(self, *args, **kw)
                return chain_design_function(self.task)
            return handler
        return chain_decorator
    
    @staticmethod
    def direct_chain_design(next_agent:BaseAgent, method:str):
        def chat_design_function(task):
            agent = next_agent(task)
            return agent.__getattribute__(method)
        return chat_design_function
            
    
    @staticmethod
    def xml_tag_content_handler(tag_name,multi=False):
        def handler_decorator(func):
            def handler(*args, **kw):
                response = func(*args, **kw)
                content = ResponseHandler.get_xml_tag_content(response, tag_name)
                return content
            async def async_handler(*args, **kw):
                response = await func(*args, **kw)
                content = ResponseHandler.get_xml_tag_content(response, tag_name)
                return content
            if multi:
                return async_handler
            return handler
        return handler_decorator

    @staticmethod
    def xml_tag_list_content_handler(tag_name,multi=False):
        def handler_decorator(func):
            def handler(*args, **kw):
                response = func(*args, **kw)
                content = ResponseHandler.get_xml_tag_list_content(response, tag_name)
                return content
            async def async_handler(*args, **kw):
                response = await func(*args, **kw)
                content = ResponseHandler.get_xml_tag_list_content(response, tag_name)
                return content
            if multi:
                return async_handler
            return handler
        return handler_decorator
    
    @staticmethod
    def multi_xml_tag_content_handler(multi=False,**tags):
        def handler_decorator(func):
            def handler(*args, **kw):
                response = func(*args, **kw)
                result = {}
                for key, tag_name in tags.items():
                    result[key] = ResponseHandler.get_xml_tag_content(response, tag_name)
                return result
            async def async_handler(*args, **kw):
                response = await func(*args, **kw)
                result = {}
                for key, tag_name in tags.items():
                    result[key] = ResponseHandler.get_xml_tag_content(response, tag_name)
                return result
            if multi:
                return async_handler
            return handler
        return handler_decorator

class ResponseChecker:
    @staticmethod
    def xml_tag_checker(tag_name,count=1):
        def checker(response):
            result = re.findall(f'<{tag_name}>(.*?)</{tag_name}>', response, re.S)
            return len(result) == count
        return checker
    
    @staticmethod
    def syntax_error_checker(tag_name):
        def checker(response):
            code = ResponseHandler.get_xml_tag_content(response,tag_name)
            try:
                exec(code)
                return True
            except:
                return False
        return checker
        
    @staticmethod
    def xml_tag_list_checker(tag_name):
        def checker(response):
            result = re.findall(f'<{tag_name}>(.*?)</{tag_name}>', response, re.S)
            return len(result) >= 1
        return checker
    
    @staticmethod
    def xml_content_options_checker(tag_name,options=["YES","NO"],upper=True):
        def checker(response):
            content: str = ResponseHandler.get_xml_tag_content(response,tag_name).strip()
            if upper:
                content = content.upper()
            return content in options
        return checker
    
    @staticmethod
    def xml_content_integer_checker(tag_name):
        def checker(response):
            content: str = ResponseHandler.get_xml_tag_content(response,tag_name)
            return content.isdigit()
        return checker
    
    @staticmethod
    def multi_checker(*checkers):
        def checker(response):
            for sub_checker in checkers:
                if not sub_checker(response):
                    return False
            return True
        return checker
    
class Linguist(BaseAgent):
    system = linguist_system
    actions_template={
        "initial":{
            "prompt":linguist_prompt,
            "keyword": ["prompt"],
        }
    }
    def __init__(self, task:Task) -> None:
        super().__init__(task)

    @BaseAgent.status_update("is_English_question")
    @ResponseHandler.assert_xml_tag_equal_handler("RESULT", "YES")
    @BaseAgent.retry(check_function=ResponseChecker.multi_checker(
        ResponseChecker.xml_tag_checker("RESULT"), ResponseChecker.xml_content_options_checker("RESULT")
    ))
    def check_English_task(self):
        question = self.task.question
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={"prompt":question})
        response = asyncio.run(session.chat(prompt))
        return response
    
class Translator(BaseAgent):
    system = translator_system
    actions_template={
        "initial":{
            "prompt":translator_prompt,
            "keyword": ["prompt"],
        }
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)
    
    @BaseAgent.status_update("question")
    @ResponseHandler.xml_tag_content_handler("PROMPT")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("PROMPT"))
    def translate_question(self):
        if self.task.status.get("is_English_question"):
            return f"<PROMPT>{self.task.question}</PROMPT>"
        question = self.task.question
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={"prompt":question})
        response = asyncio.run(session.chat(prompt))
        return response
    
class PromptEngineer(BaseAgent):
    system = prompt_engineer_system
    actions_template={
        "initial":{
            "prompt":prompt_engineer_prompt,
            "keyword": ["prompt"],
        }
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)

    @BaseAgent.status_update("refine_question")
    @ResponseHandler.xml_tag_content_handler("PROMPT")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("PROMPT"))
    def refine_prompt(self):
        question = self.task.status.get("question")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={"prompt":question})
        response = asyncio.run(session.chat(prompt))
        return response
        
class FileAnalyst(BaseAgent):
    system = file_agent_system
    actions_template={
        "initial":{
            "prompt":file_agent_prompt,
            "keyword": ["prompt","file"],
        },
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)

    @ResponseHandler.xml_tag_content_handler("ANALYSE", multi=True)
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("ANALYSE"), multi=True)
    async def analyse_file(self, file):
        question = self.task.status.get("question")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "prompt":question,
            "file":file
        })
        response = await session.chat(prompt)
        return response
        
    async def analyse_files(self):
        files = self.task.file_list
        tasks = []
        result = {}
        for file in files:
            tasks.append({
                "file":file,
                "task":asyncio.create_task(self.analyse_file(file))
            })
        for task in tasks:
            result[task["file"]] = await task["task"]
        self.task.status.file_analysis = result
        

class ToolScorer(BaseAgent):
    system = tool_scorer_system
    actions_template={
        "initial":{
            "prompt":tool_scorer_prompt,
            "keyword": ["prompt","toolname","documentation"],
        },
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self.temperature = 0
        
    @ResponseHandler.multi_xml_tag_content_handler(multi=True,score="SCORE",reason="REASON")
    @BaseAgent.retry(check_function=ResponseChecker.multi_checker(
        ResponseChecker.xml_tag_checker("SCORE"),
        ResponseChecker.xml_tag_checker("REASON"),
        ResponseChecker.xml_content_integer_checker("SCORE"),
    ), multi=True)
    async def tool_score(self, tool):
        document = self.task.status.tools[tool].get("document")
        question = self.task.status.get("question")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "prompt":question,
            "toolname":tool,
            "documentation":document
        })
        if self.config.USE_MEMORY:
            prompt += memory_retriever.match(tool,self.task.status.raw_question, self.task.status.task_id, k=5)
        response = await session.chat(prompt)
        return response
    
    async def tools_score(self):
        tools = self.task.status.tools
        tasks = []
        for tool in tools:
            tasks.append({
                "tool":tool,
                "task":asyncio.create_task(self.tool_score(tool))
            })
        for task in tasks:
            response = await task["task"]
            response["score"] = int(response["score"])
            tools[task["tool"]].update(response)

class ToolDescriptor(BaseAgent):
    system = bioinformatician_system
    actions_template={
        "initial":{
            "prompt":bioinformatician_prompt,
            "keyword": ["prompt","toolname","documentation"],
        },
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)
    
    def get_need_describe_tools(self):
        result = []
        tools = self.task.status.tools
        key = "score" if not self.task.status.rescored else "re_score"
        for tool in tools:
            if "description" in tool: continue
            if tools[tool][key] >= self.config.HIGHSCORE_TOOL_THRESHOLD:
                result.append(tool)
        return result
    
    @ResponseHandler.xml_tag_content_handler("DESCRIPTION", multi=True)
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("DESCRIPTION"), multi=True)
    async def tool_describe(self, tool):
        document = self.task.status.tools[tool].get("document")
        question = self.task.status.get("question")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "prompt":question,
            "toolname":tool,
            "documentation":document
        })
        response = await session.chat(prompt)
        return response
    
    async def tools_describe(self):
        need_describe_tools = self.get_need_describe_tools()
        tools = self.task.status.tools
        tasks = []
        for tool in need_describe_tools:
            tasks.append({
                "tool":tool,
                "task":asyncio.create_task(self.tool_describe(tool))
            })
        for task in tasks:
            response = await task["task"]
            tools[task["tool"]]["description"] = response

class ToolReScorer(BaseAgent):
    system = tool_rescorer_system
    actions_template={
        "initial":{
            "prompt":tool_rescorer_prompt,
            "keyword": ["prompt","origin_score","toolname","documentation"],
        },
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)

    def get_origin_score(self):
        tools = self.task.status.tools
        result = []
        for tool in tools:
            if tools[tool]["score"] >= self.config.HIGHSCORE_TOOL_THRESHOLD:
                result.append({
                    "toolname":tool,
                    "suggestion":tools[tool]["description"]
                })
        return json.dumps(result,ensure_ascii=False)

    @ResponseHandler.multi_xml_tag_content_handler(multi=True,re_score="SCORE",re_reason="REASON")
    @BaseAgent.retry(check_function=ResponseChecker.multi_checker(
        ResponseChecker.xml_tag_checker("SCORE"),
        ResponseChecker.xml_tag_checker("REASON"),
        ResponseChecker.xml_content_integer_checker("SCORE"),
    ), multi=True)
    async def tool_score(self, tool, origin_score):
        document = self.task.status.tools[tool].get("document")
        question = self.task.status.get("question")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "prompt":question,
            "toolname":tool,
            "documentation":document,
            "origin_score":origin_score
        })
        if self.config.USE_MEMORY:
            prompt += memory_retriever.match(tool,self.task.status.raw_question, self.task.status.task_id, k=5)
        response = await session.chat(prompt)
        return response
    
    async def tools_score(self):
        origin_score = self.get_origin_score()
        tools = self.task.status.tools
        tasks = []
        for tool in tools:
            tasks.append({
                "tool":tool,
                "task":asyncio.create_task(self.tool_score(tool, origin_score))
            })
        for task in tasks:
            response = await task["task"]
            response["re_score"] = int(response["re_score"])
            tools[task["tool"]].update(response)
        self.task.status.rescored = True

class WorkflowDesigner(BaseAgent):
    system = workflow_architect_system
    actions_template={
        "initial":{
            "prompt":workflow_architect_prompt,
            "keyword": ["prompt","analysis_result","tool_list"],
        },
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self.model = self.config.SUPER_LLM_MODEL
    
    def get_tools_info(self):
        tools = self.task.status.tools
        tools_info = []
        for tool in tools:
            if tools[tool]["re_score"] >= self.config.WORKFLOW_USED_TOOL_THRESHOLD:
                tools_info.append({
                    "tool": tool,
                    "documentation": tools[tool]["document"],
                })
                if "description" in tools[tool]:
                    tools_info[-1]["description"]=tools[tool]["description"]
        return tools_info

    @BaseAgent.status_update(key="workflow")
    @ResponseHandler.xml_tag_content_handler("RESULT")
    @BaseAgent.status_update(key="raw_workflow")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("RESULT"))
    def workflow_design(self):
        tools_info = self.get_tools_info()
        question = self.task.status.get("question")
        file_analysis = self.task.status.get("file_analysis")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "prompt":question,
            "analysis_result":json.dumps(file_analysis,ensure_ascii=False),
            "tool_list":json.dumps(tools_info,ensure_ascii=False)
        })
        prompt += self.task.file_appendix
        if self.config.USE_MEMORY:
            prompt += memory_retriever.match("workflow",self.task.status.raw_question, self.task.status.task_id, k=3)
        response = asyncio.run(session.chat(prompt))
        return response

class ToolAnasyst(BaseAgent):
    system = tool_suggestion_system
    actions_template={
        "initial":{
            "prompt":tool_suggestion_prompt,
            "keyword": ["prompt","workflow","tool_info","tool"],
        },
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self.model = self.config.SUPER_LLM_MODEL

    def get_tool_used(self, workflow):
        tools = self.task.status.tools
        tool_used = {}
        for tool in tools:
            if tool in workflow:
                tool_used[tool] = {
                    "tool":tool,
                    "documentation":tools[tool]["document"]
                }
        self.task.status.tool_used = tool_used
        return tool_used
    
    @ResponseHandler.xml_tag_content_handler("SUGGESTION", multi=True)
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("SUGGESTION"), multi=True)
    async def tool_analyse(self, tool, workflow):
        question = self.task.status.get("question")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "prompt":question,
            "tool":tool,
            "workflow":workflow,
            "tool_info":self.tool_info
        })
        response = await session.chat(prompt)
        return response

    async def tools_analyse(self):
        workflow = self.task.status.get("workflow")
        tools = self.get_tool_used(workflow)
        self.tool_info = json.dumps(tools, ensure_ascii=False)
        tasks = []
        for tool in tools:
            tasks.append({
                "tool":tool,
                "task":asyncio.create_task(self.tool_analyse(tool, workflow))
            })
        for task in tasks:
            response = await task["task"]
            tools[task["tool"]]["suggestion"] = response

class WorkflowFormatter(BaseAgent):
    system = format_desinger_system
    actions_template={
        "initial":{
            "prompt":format_desinger_prompt,
            "keyword": ["prompt","workflow"],
        },
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)

    @BaseAgent.status_update("workflow_stages")
    @ResponseHandler.xml_tag_list_content_handler("STAGE")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_list_checker("STAGE"))
    def workflow_format(self):
        question = self.task.status.get("question")
        workflow = self.task.status.get("workflow")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "prompt":question,
            "workflow":workflow
        })
        response = asyncio.run(session.chat(prompt))
        return response

class ActionDesigner(BaseAgent):
    system = action_architecture_expert_system
    actions_template={
        "initial":{
            "prompt":action_architecture_expert_prompt,
            "keyword": ["prompt","workflow","tool_suggestion_data","stage"],
        },
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self.model = self.config.SUPER_LLM_MODEL

    @ResponseHandler.xml_tag_content_handler("STAGE", multi=True)
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("STAGE"), multi=True)
    async def action_design(self, stage):
        question = self.task.status.get("question")
        workflow = self.task.status.get("workflow")
        tool_suggestion_data = json.dumps(self.task.status.tool_used, ensure_ascii=False)
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "prompt":question,
            "stage":stage,
            "workflow":workflow,
            "tool_suggestion_data":tool_suggestion_data
        })
        response = await session.chat(prompt)
        return response

    async def actions_design(self):
        stages = self.task.status.get("workflow_stages")
        tasks = []
        actions = []
        for stage in stages:
            tasks.append({
                "stage":stage,
            })
        
        for task in tasks:
            actions.append({
                "stage":task["stage"],
            })
        self.task.status.actions = actions

class MermaidDesigner(BaseAgent):
    system = mermaid_system
    actions_template={
        "initial":{
            "prompt":mermaid_prompt,
            "keyword": ["workflow"],
        },
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self.model = self.config.SUPER_LLM_MODEL

    @BaseAgent.status_update("mermaid_code")
    @ResponseHandler.xml_tag_content_handler("CODE")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("CODE"))
    def mermaid_design(self):
        workflow = self.task.status.get("workflow")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "workflow":workflow
        })
        response = asyncio.run(session.chat(prompt))
        return response

class Programmer(BaseAgent):
    programmer_system = programmer_system
    tester_system = tester_system
    programmer_template = {
        "initial":{
            "prompt":programmer_prompt,
            "keyword": ["prompt","workflow","tool_suggestion_data","subtask","name"],
        },
        "func_fix":{
            "prompt":programmer_func_fix,
            "keyword": ["function"]
        },
        "fail_test":{
            "prompt":programmer_fail_test,
            "keyword": ["suggestion"]
        }
    }
    tester_template = {
        "initial":{
            "prompt":tester_prompt,
            "keyword": ["prompt","workflow","tool_suggestion_data","subtask","code","function","resource_pool"],
        },
        "rethink":{
            "prompt":tester_rethink,
            "keyword": ["info"]
        },
        "error":{
            "prompt":tester_error,
            "keyword": ["info"]
        },
        "description":{
            "prompt":tester_description,
            "keyword": ["output"]
        },
        "fail_test":{
            "prompt":tester_fail_test,
            "keyword": ["suggestion"]
        },
        "fix":{
            "prompt":tester_fix,
            "keyword": []
        },
    }

    necessary_system = necessary_system
    necessary_template={
        "initial":{
            "prompt":necessary_prompt,
            "keyword": ["prompt","workflow","subtask"],
        },
    }

    split_system = split_again_system
    split_template = {
        "initial":{
            "prompt":split_again_prompt,
            "keyword": ["prompt","workflow","subtask"],
        },
    }

    workflow_fix_system = workflow_fix_system
    workflow_fix_template = {
        "ignore":{
            "prompt":workflow_fix_ignore,
            "keyword":["prompt","workflow","subtask","error"]
        },
        "split":{
            "prompt":workflow_fix_split,
            "keyword":["prompt","workflow","subtask","error"]
        },
        "normal":{
            "prompt":workflow_fix_normal,
            "keyword":["prompt","workflow","subtask","error"]
        }
    }

    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self.model = self.config.SUPER_LLM_MODEL

        self.programmer_extra_prompt = ""
        self.tester_extra_prompt = ""

    def get_tool_suggestion_data(self):
        tools = self.task.status.tool_used
        result = []
        for tool in tools:
            result.append({
                "tool":tool,
                "documentation":tools[tool]["documentation"]
            })
        return json.dumps(result,ensure_ascii=False)

    @ResponseHandler.xml_tag_content_handler("CODE")
    @BaseAgent.retry(check_function=ResponseChecker.multi_checker(
        ResponseChecker.xml_tag_checker("CODE")
    ))
    def get_programmer_code(self, subtask, name, session):
        question = self.task.status.get("question")
        workflow = self.task.status.get("workflow")
        tool_suggestion_data = self.get_tool_suggestion_data()
        prompt = self.format_template(data={
            "prompt":question,
            "workflow":workflow,
            "subtask":subtask,
            "tool_suggestion_data":tool_suggestion_data,
            "name":name
        },templates=self.programmer_template)
        if name.endswith("0"):
            prompt += self.task.file_appendix
        if self.config.USE_MEMORY:
            prompt += memory_retriever.match("action",subtask, self.task.status.task_id, k=5)
        response = asyncio.run(session.chat(prompt))
        return response
    
    @ResponseHandler.xml_tag_content_handler("CODE")
    @BaseAgent.retry(check_function=ResponseChecker.multi_checker(
        ResponseChecker.xml_tag_checker("CODE")
    ))
    def get_tester_code(self, subtask, code, function, session):
        question = self.task.status.get("question")
        workflow = self.task.status.get("workflow")
        tool_suggestion_data = self.get_tool_suggestion_data()
        resource_pool = json.dumps(self.task.status.resource_pool, ensure_ascii=False)
        prompt = self.format_template(data={
            "prompt":question,
            "workflow":workflow,
            "subtask":subtask,
            "tool_suggestion_data":tool_suggestion_data,
            "function":function,
            "code":code,
            "resource_pool":resource_pool,
        }, templates=self.tester_template)
        if function.endswith("0"):
            prompt += self.task.file_appendix
        if self.config.USE_MEMORY:
            prompt += memory_retriever.match("test",subtask, self.task.status.task_id, k=5)
        response = asyncio.run(session.chat(prompt))
        return response
    
    @ResponseHandler.xml_tag_content_handler("SUGGESTION")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("SUGGESTION"))
    def get_fix_suggestion(self, subtask, error, chat_action):
        question = self.task.status.get("question")
        workflow = self.task.status.get("workflow")
        prompt = self.format_template(action=chat_action,data={
            "prompt":question,
            "workflow":workflow,
            "subtask":subtask,
            "error":error
        },templates=self.workflow_fix_template)
        session = self.create_chatsession(self.workflow_fix_system)
        response = asyncio.run(session.chat(prompt))
        return response
    
    @ResponseHandler.xml_tag_content_handler("CODE")
    @BaseAgent.retry(check_function=ResponseChecker.multi_checker(
        ResponseChecker.xml_tag_checker("CODE")
    ))
    def fix_programming_code(self, suggestion, session:ChatSession):
        prompt = self.format_template(action="fail_test",data={
            "suggestion":suggestion
        }, templates=self.tester_template)
        response = asyncio.run(session.chat(prompt))
        return response
    
    @ResponseHandler.xml_tag_content_handler("CODE")
    @BaseAgent.retry(check_function=ResponseChecker.multi_checker(
        ResponseChecker.xml_tag_checker("CODE")
    ))
    def fix_test_code(self, session:ChatSession):
        prompt = self.format_template(action="fix",data={}, templates=self.tester_template)
        response = asyncio.run(session.chat(prompt))
        return response

    
    @ResponseHandler.multi_xml_tag_content_handler(reason="REASON")
    @BaseAgent.retry(check_function=ResponseChecker.multi_checker(
        ResponseChecker.xml_tag_checker("REASON")
    ))
    def get_reason(self, info, chat_action, session:ChatSession):
        prompt = self.format_template(action=chat_action,data={
            "info":info
        }, templates=self.tester_template)
        response = asyncio.run(session.chat(prompt))
        return response
    
    @ResponseHandler.multi_xml_tag_content_handler(description="DESCRIPTION",output="OUTPUT",type="TYPE")
    @BaseAgent.retry(check_function=ResponseChecker.multi_checker(
        ResponseChecker.xml_tag_checker("DESCRIPTION"),
        ResponseChecker.xml_tag_checker("OUTPUT"),
        ResponseChecker.xml_tag_checker("TYPE")
    ))
    def resource_analyse(self, data, session:ChatSession|None=None):
        if session is None:
            session = self.create_chatsession("You are a tester")
        prompt = self.format_template(action="description",data={
            "output":json.dumps(data)
        }, templates=self.tester_template)
        response = asyncio.run(session.chat(prompt))
        return response
    
    @ResponseHandler.assert_xml_tag_equal_handler("RESULT", "NO")
    @BaseAgent.retry(check_function=ResponseChecker.multi_checker(
        ResponseChecker.xml_tag_checker("RESULT"), ResponseChecker.xml_content_options_checker("RESULT")
    ))
    def check_can_ignore(self, subtask):
        question = self.task.status.get("question")
        workflow = self.task.status.get("workflow")
        prompt = self.format_template(data={
            "prompt":question,
            "workflow":workflow,
            "subtask":subtask
        },templates=self.necessary_template)
        session = self.create_chatsession(self.necessary_system)
        response = asyncio.run(session.chat(prompt))
        return response
    

    @ResponseHandler.assert_xml_tag_equal_handler("RESULT", "YES")
    @BaseAgent.retry(check_function=ResponseChecker.multi_checker(
        ResponseChecker.xml_tag_checker("RESULT"), ResponseChecker.xml_content_options_checker("RESULT")
    ))
    def check_can_split(self, subtask):
        question = self.task.status.get("question")
        workflow = self.task.status.get("workflow")
        prompt = self.format_template(data={
            "prompt":question,
            "workflow":workflow,
            "subtask":subtask
        },templates=self.split_template)
        session = self.create_chatsession(self.split_system)
        response = asyncio.run(session.chat(prompt))
        return response
    
    def action_execute(self, code, test_func_name):
        code_task_id = push_code(code, test_func_name, self.config, official=self.task.official)
        output = get_code_output(code_task_id, self.config)
        return output
    
    def action_task(self, action, index):
        programmer_session = self.create_chatsession(self.programmer_system)
        programmer_code = self.get_programmer_code(action, f"action{index}", programmer_session)
        tester_session = self.create_chatsession(self.tester_system)
        tester_code = self.get_tester_code(action, programmer_code, f"test{index}", tester_session)
        action_code = get_action_code(programmer_code, tester_code)
        result, data = self.action_task_posting(
            action, 
            programmer_code, 
            tester_code, 
            index, 
            programmer_session, 
            tester_session
        )
        if result:
            #? ######################################################
            self.task.status.code[f"stage{index}"] = action_code
            self.task.status.code_result["partial_result"].append({
                "action": index,
                "finish": True,
                "code": action_code,
                "files":[], # TODO
                "path":self.config.TASK_DIR
            })
            self.task.status.status_update("code")
            #? ######################################################
            return True, action_code
        retry_times = 1
        while retry_times < self.config.ACTION_RETRY_TIMES:
            #? ######################################################
            self.task.status.code_result["partial_result"].append({
                "action": index,
                "finish": False,
                "code": action_code,
                "retry": retry_times, 
                "files":[],#TODO
                "path":self.config.TASK_DIR
            })
            self.task.status.status_update("code")
            #? ######################################################
            result, data = self.action_task_posting(
                action,
                data["programmer_code"],
                data["tester_code"],
                index,
                data["programmer_session"],
                data["tester_session"]
            )
            action_code = get_action_code(data["programmer_code"], data["tester_code"])
            if result:
                self.task.status.code[f"stage{index}"] = action_code
                self.task.status.code_result["partial_result"].append({
                    "action": index,
                    "finish": True,
                    "code": action_code,
                    "files":[],#TODO
                    "path":self.config.TASK_DIR
                })
                self.task.status.status_update("code")
                return True, action_code
            retry_times += 1
        self.task.status.code_result["partial_result"].append({
            "action": index,
            "finish": False,
            "code": action_code,
            "retry": retry_times, 
            "files":[],
            "path":self.config.TASK_DIR,
        })
        self.task.status.status_update("code")
        can_ignore = self.check_can_ignore(action)
        can_split = self.check_can_split(action)
        can_split = False
        if can_ignore:
            chat_action = "ignore"
        elif can_split:
            chat_action = "split"
        else:
            chat_action = "normal"
        suggestion = self.get_fix_suggestion(action,data["error_reason"], chat_action)
        return False, suggestion
        
    def action_task_posting(self, action, programmer_code, tester_code, index, programmer_session, tester_session):
        action_code = get_action_code(programmer_code, tester_code)
        output = self.action_execute(action_code, f"test{index}")
        result = output["result"]
        excepted = output["excepted"]
        data = output["data"]
        if not result:
            chat_action = "error" if excepted else "rethink"
            response = self.get_reason(data, chat_action, tester_session)
            test_result = False
            test_reason = response["reason"]
            if test_result:
                tester_code = self.fix_test_code(tester_session)
            else:
                programmer_code = self.fix_programming_code(test_reason, programmer_session)
                tester_session = self.create_chatsession(self.tester_system)
                tester_code = self.get_tester_code(action, programmer_code, f"test{index}", tester_session)
            return False, {
                "programmer_code": programmer_code,
                "tester_code": tester_code,
                "programmer_session": programmer_session,
                "tester_session": tester_session,
                "output":output,
                "error_reason":test_reason,
            }
        else:
            response = self.resource_analyse(data, tester_session)
            description = response["description"]
            output = response["output"]
            _type = response["type"]
            self.task.status.resource_pool.append({
                "item":data,
                "info":output,
                "type":_type,
                "description":description
            })
            return True, {
                "programmer_code": programmer_code,
                "tester_code": tester_code,
            }

    def programming(self):
        self.task.status.resource_pool = []
        self.task.status.code_result = {
            "partial_result" : [],
        }
        total_result = {
            "code_info":[],
            "path":self.config.TASK_DIR,
            "files":[]
        }
        for k,v in self.task.status.file_analysis.items():
            self.task.status.resource_pool.append({
                "item":k,
                "info":k,
                "type":"file",
                "description":v
            })
        actions = self.task.status.get("actions")
        for index,action in enumerate(actions):
            ok, data = self.action_task(action["stage"], index)
            total_result["code_info"].append({
                "task":action["stage"],
                "code":data
            })
            if not ok:
                return False, data
        self.task.status.code_result["total_result"] = total_result
        self.task.status.status_update("code")
        return True, None
    
class WorkflowReDesigner(BaseAgent):
    system = re_workflow_system
    actions_template={
        "initial":{
            "prompt":re_workflow_prompt,
            "keyword": ["prompt","analysis_result","tool_list","workflow","suggestion"],
        },
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self.model = self.config.SUPER_LLM_MODEL

    def get_tools_info(self):
        tools = self.task.status.tools
        tools_info = []
        for tool in tools:
            if tools[tool]["re_score"] >= self.config.WORKFLOW_USED_TOOL_THRESHOLD:
                tools_info.append({
                    "tool": tool,
                    "documentation": tools[tool]["document"],
                })
                if "description" in tools[tool]:
                    tools_info[-1]["description"]=tools[tool]["description"]
        return tools_info

    @BaseAgent.status_update(key="workflow")
    @ResponseHandler.xml_tag_content_handler("RESULT")
    @BaseAgent.status_update(key="raw_workflow")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("RESULT"))
    def workflow_redesign(self, suggestion):
        tools_info = self.get_tools_info()
        question = self.task.status.get("question")
        file_analysis = self.task.status.get("file_analysis")
        workflow = self.task.status.get("raw_workflow")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "prompt":question,
            "workflow":workflow,
            "suggestion":suggestion,
            "analysis_result":json.dumps(file_analysis,ensure_ascii=False),
            "tool_list":json.dumps(tools_info,ensure_ascii=False)
        })
        if self.config.USE_MEMORY:
            prompt += memory_retriever.match("workflow",self.task.status.raw_question, self.task.status.task_id, k=3)
        response = asyncio.run(session.chat(prompt))
        return response
        
class SummaryAnalyst(BaseAgent):
    system = summary_system
    actions_template={
        "initial":{
            "prompt":summary_prompt,
            "keyword": ["prompt","workflow","resource_pool"],
        },
    }
    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self.model = self.config.SUPER_LLM_MODEL

    @BaseAgent.status_update("summary")
    @ResponseHandler.xml_tag_content_handler("SUMMARY")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("SUMMARY"))
    def summary(self):
        question = self.task.status.get("question")
        workflow = self.task.status.get("workflow")
        resource_pool = json.dumps(self.task.status.resource_pool, ensure_ascii=False)

        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "prompt":question,
            "workflow":workflow,
            "resource_pool":resource_pool
        })
        response = asyncio.run(session.chat(prompt))
        return response
