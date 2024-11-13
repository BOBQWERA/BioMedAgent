import json
import time
import traceback

from agent import *
from config import Config
from server.base import BaseServer

from utils import rprint, knowledge_base


class BatchTaskExecutor(BaseServer):
    SERVER_KEY = "batchtask-v0.2"

    def __init__(self) -> None:
        super().__init__()

    def get_task(self):
        task_id = self.r.rpop("biomedagent:pool:batch_task:0.2")
        if not task_id:
            return False, None
        data = self.r.get(f"biomedagent:info:batch_task:{task_id}")
        data = json.loads(data)
        data["status"] = 'start'
        self.save_data(task_id, data)
        return True, data
        
    def save_data(self, task_id, data):
        self.r.set(f"biomedagent:info:batch_task:{task_id}",json.dumps(data))
    
    def execute(self, data):
        task_id = data["task_id"]
        print(task_id)
        update = bool(data.get("update"))
        is_batch = bool(data.get("batch"))
        rprint(str(is_batch))
        start_time = time.time()
        config = Config.set_task(task_id)
        config.ECHO_INFO = False 
        config.USE_MEMORY = False
        config.USE_FILE_APPENDIX = False
        task = Task(data, config, update, official=is_batch)
        task.status.raw_question = task.question
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
        mermaid_designer = MermaidDesigner(task)

        try:
            error = "no error"
            task.status.status_update("start")
            linguist.check_English_task()
            translator.translate_question()
            prompt_engineer.refine_prompt()
            task.status.status_update("improve_prompt")
            asyncio.run(file_analyst.analyse_files())
            asyncio.run(tool_scorer.tools_score())
            asyncio.run(tool_descriptor.tools_describe())
            asyncio.run(tool_rescorer.tools_score())
            asyncio.run(tool_descriptor.tools_describe())
            task.status.status_update("tool_score")
            workflow_designer.workflow_design()
            # mermaid_designer.mermaid_design()
            asyncio.run(tool_analyst.tools_analyse())
            workflow_formatter.workflow_format()
            asyncio.run(action_designer.actions_design())
            task.status.status_update("workflow")
            success, suggestion = programmer.programming()
            retry_times = 1
            while not success and retry_times < 3:
                if retry_times >= 3:
                    programmer.tester_extra_prompt = """
    You'll want to simulate the output via the mock technique and try to write code that generates a virtual empty file, it's not necessary to actually accomplish the actual function.
    """
                retry_times += 1
                task.backtrack_update()
                workflow_redesigner.workflow_redesign(suggestion)
                asyncio.run(tool_analyst.tools_analyse())
                workflow_formatter.workflow_format()
                asyncio.run(action_designer.actions_design())
                task.status.status_update("workflow")
                success, suggestion = programmer.programming()
            if not success: raise Exception("任务失败")
            summary_analyst.summary()
            task.status.status_update("summary")
            time.sleep(3)
            task.status.status_update("completed")
        except Exception as e:
            traceback.print_exc()
            success = False
            error = repr(e)
            task.status.error = error
            task.status.status_update("failed")
        
        

        task.status.success = success
        task.status.use_time = int(time.time()-start_time)

        data["status"] = success
        data["finish"] = True
        self.save_data(task_id, data)
        self.r.set(f"biomedagent:result:{task_id}",json.dumps(task.status.data))