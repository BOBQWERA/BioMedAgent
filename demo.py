import os

import argparse
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

parser = argparse.ArgumentParser(description='Demo for BioMedAgent')
parser.add_argument('--task', type=str, choices=['machine_learning', 'statistics_t_test', 'statistics_qq_plot', 'visualization_survival_plot', 'visualization_violin_plot', 'omics'],
                    default='machine_learning', help='task type')
args = parser.parse_args()

def generate_question_info(task_type):
    base_info = {
        "machine_learning": {
            "question": "I have a dataset {heart_disease.csv}, the “Target” column is the target column and the other columns are the feature columns, please perform a singular value decomposition downscaling on this dataset.",
            "files": [{
                "name": "heart_disease.csv",
                "path": "data/heart_disease.csv"
            }]
        },
        "statistics_t_test": {
            "question": "There are two existing data tables, {data1.tsv} is a biomarker data table, with sample names as column names and biomarker names as row names, {group1.tsv} is a data table containing sample grouping information, where the two groups are 1 and 2, with the column name ID as sample names and the column name group as grouping information. Please use the tool t_test to perform an independent sample t-test based on this information.",
            "files": [
                {
                    "name": "data1.tsv", 
                    "path": "data/data1.tsv"
                },
                {
                    "name": "group1.tsv", 
                    "path": "data/group1.tsv"
                }
            ]
        },
        "statistics_qq_plot": {
            "question": "There is a dataset {boxplot.tsv}, Group2 column is the grouping information, which contains treat1 and treat2, please analyze whether the data in Value column of the two groupings of treat1 and treat2 have similar distribution characteristics, and plot QQ plot.",
            "files": [{
                "name": "boxplot.tsv", 
                "path": "data/boxplot.tsv"
            }]
        },
        "visualization_survival_plot": {
            "question": "There is a data table {TCGA_LIHC_survival.txt} that contains information related to patient survival. The column named OS.time represents the survival time of the patients, the column named OS indicates the survival event status of the patients, and the column named gender is a variable that affects survival. Please use the tool survival_curve to plot the survival curve based on this information.",
            "files": [{
                "name": "TCGA_LIHC_survival.txt",
                "path": "data/TCGA_LIHC_survival.txt"
            }]
        },
        "visualization_violin_plot": {
            "question": "There is a data file {plot.tsv}, the Sex column is the gender of the sample, Age_Group is the different age grouping corresponding to each gender, please use the violin plot to show the distribution of WBC for each age grouping of different genders.",
            "files": [{
                "name": "plot.tsv",
                "path": "data/plot.tsv"
            }]
        },
        "omics": {
            "question": "The following is the microarray expression data {GSM509787_E1507N.CEL.gz} of 1 sample from esophageal squamous cell carcinoma dataset GSE20347, the corresponding probe number is {GPL571}, please use the CeltoExp tool to convert the CEL microarray expression file into gene expression profile data in txt file format.",
            "files": [{
                "name": "GSM509787_E1507N.CEL.gz",
                "path": "data/GSM509787_E1507N.CEL.gz"
            }]
        },
    }
    return base_info[task_type]

question_info = generate_question_info(args.task)

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
retry_times = 1
while not ok and retry_times < 3:
    retry_times += 1
    task.backtrack_update()
    workflow_redesigner.workflow_redesign(suggestion)
    asyncio.run(tool_analyst.tools_analyse())
    workflow_formatter.workflow_format()
    asyncio.run(action_designer.actions_design())
    task.status.status_update("workflow")
    ok, suggestion = programmer.programming()
if not ok: raise Exception("Task failed")
summary_analyst.summary()