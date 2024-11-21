import os

os.environ["OPENAI_BASE_URL"] = ""
os.environ["OPENAI_API_KEY"] = ""

import threading

from server.gpt import GPTServer

server = GPTServer()
thread = threading.Thread(target=server.run)
thread.start()

from server.code_executor import CodeExecutor

server = CodeExecutor()
thread = threading.Thread(target=server.run)
thread.start()

from agent import *
from config import Config
from utils import generate_task_id


config = Config(generate_task_id())

question_info = {
    "question":"For the vcf file {demo.vcf}, perform mutation annotation to generate the maf file",
    "files":[
        {
            "name":"demo.vcf",
            "path":"data/demo.vcf"
        }
    ]
}

os.makedirs(
    os.path.join(config.TASK_DIR,config.get_task())
)


task = Task(question_info, config)
linguist = Linguist(task)
translator = Translator(task)
prompt_engineer = PromptEngineer(task)
file_analyst = FileAnalyst(task)
tool_scorer = ToolScorer(task)
tool_descriptor = ToolDescriptor(task)
tool_rescorer = ToolReScorer(task)
workflow_designer = WorkflowDesigner(task)
tool_analyst = ToolAnasyst(task)
workflow_formatter = WorkflowFormatter(task)
action_designer = ActionDesigner(task)
programmer = Programmer(task)
summary_analyst = SummaryAnalyst(task)
workflow_redesigner = WorkflowReDesigner(task)

linguist.check_English_task()
translator.translate_question()
prompt_engineer.refine_prompt()
asyncio.run(file_analyst.analyse_files())
asyncio.run(tool_scorer.tools_score())
asyncio.run(tool_descriptor.tools_describe())
asyncio.run(tool_rescorer.tools_score())
asyncio.run(tool_descriptor.tools_describe())
workflow_designer.workflow_design()
asyncio.run(tool_analyst.tools_analyse())
workflow_formatter.workflow_format()
asyncio.run(action_designer.actions_design())
ok, suggestion = programmer.programming()

if not ok:
    workflow_redesigner.workflow_redesign(suggestion)
summary_analyst.summary()