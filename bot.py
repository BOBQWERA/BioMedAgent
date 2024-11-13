import asyncio

from agent import BaseAgent, ResponseHandler, ResponseChecker
from config import Config

from prompt import (
    request_analyse_prompt,
    request_analyse_system,
    workflow_analyse_prompt,
    workflow_analyse_system,
    tool_suggestion_system,
    tool_suggestion_prompt,
    mermaid_system,
    mermaid_prompt
)

class RequestAnalyst(BaseAgent):
    system = request_analyse_system
    actions_template = {
        "initial":{
            "prompt":request_analyse_prompt,
            "keyword": [
                "tool_name",
                "tool_doc",
                "tool_code",
                "data_info"
            ],
        }
    }

    def __init__(self) -> None:
        self.config = Config()
        self.config.SAVE_LOG = False
        self.temperature = 0.2
        self.model = self.config.SUPER_LLM_MODEL

    @ResponseHandler.xml_tag_content_handler("PROMPT")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("PROMPT"))
    def request_analyse(self, name, doc, code, info):
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "tool_name":name,
            "tool_doc":doc,
            "tool_code":code,
            "data_info":info,
        })
        response = asyncio.run(session.chat(prompt))
        return response
    
class WorkflowAnalyst(BaseAgent):
    system = workflow_analyse_system #TODO
    actions_template={
        "initial":{
            "prompt":workflow_analyse_prompt, #TODO
            "keyword": [
                "question",
                "tool_name",
                "tool_doc",
                "action_test_code"
                ], #TODO
        },
    }
    def __init__(self) -> None:
        self.config = Config()
        self.config.SAVE_LOG = False
        self.temperature = 0.2
        self.model = self.config.SUPER_LLM_MODEL

    @ResponseHandler.xml_tag_content_handler("RESULT")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("RESULT"))
    def workflow_analyse(self, question, tool_name, tool_doc, action_test_code):
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "question": question,
            "tool_name": tool_name,
            "tool_doc": tool_doc,
            "action_test_code": action_test_code
        })
        return asyncio.run(session.chat(prompt))
    
class SuggestionAnalyst(BaseAgent):
    system = tool_suggestion_system
    actions_template={
        "initial":{
            "prompt":tool_suggestion_prompt,
            "keyword": [
                "prompt",
                "tool",
                "workflow",
                "tool_info"
            ]
        },
    }
    def __init__(self) -> None:
        self.config = Config()
        self.config.SAVE_LOG = False
        self.temperature = 0.2
        self.model = self.config.SUPER_LLM_MODEL
    
    @ResponseHandler.xml_tag_content_handler("SUGGESTION")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("SUGGESTION"))
    def tool_suggestion_analyse(self, question, tool, workflow, tool_info):
        # question = self.task.status.get("question")
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "prompt":question,
            "tool":tool,
            "workflow":workflow,
            "tool_info":tool_info
        })
        response = asyncio.run(session.chat(prompt))
        return response

class MermaidDesigner(BaseAgent):
    system = mermaid_system
    actions_template={
        "initial":{
            "prompt":mermaid_prompt,
            "keyword": ["workflow"],
        },
    }
    def __init__(self) -> None:
        self.config = Config()
        self.config.SAVE_LOG = False
        self.temperature = 0.2
        self.model = self.config.SUPER_LLM_MODEL

    @ResponseHandler.xml_tag_content_handler("CODE")
    @BaseAgent.retry(check_function=ResponseChecker.xml_tag_checker("CODE"))
    def mermaid_design(self, workflow):
        session = self.create_chatsession(self.system)
        prompt = self.format_template(data={
            "workflow":workflow
        })
        response = asyncio.run(session.chat(prompt))
        return response


    