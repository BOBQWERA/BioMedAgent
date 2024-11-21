import os
import json
from datetime import datetime
from uuid import uuid4

from colorama import Fore, Style
from config import Config

rprint = lambda x: print(Fore.RED + x + Style.RESET_ALL)
gprint = lambda x: print(Fore.GREEN + x + Style.RESET_ALL)
yprint = lambda x: print(Fore.YELLOW + x + Style.RESET_ALL)

def time_dir():
    now = datetime.now()
    return os.path.join(
        f"{now.year}-{now.month}",f"{now.day}"
    )

def generate_task_id():
    return f"{uuid4()}"

def get_action_code(programmer_code, tester_code):
    total_code = f"""

{programmer_code}

{tester_code}
"""
    return total_code


def knowledge_base(item_key:str, query_key:str, query_value:str, question_id:str, task_id = None):

    r = Config().get_redis_connect()
    memory_id = generate_task_id()
    r.lpush(
        f"{Config.REDIS_MEMORY_STORAGE_KEY}:{item_key}", json.dumps({
            "key":query_key,
            "value":query_value,
            "id":memory_id,
            "question_id":question_id,
            "task_id":task_id,
            "item_key":item_key
        })
    )
    r.hset(Config.REDIS_INSTANCE_INFO_KEY, memory_id, json.dumps({
        "key":query_key,
        "value":query_value,
        "id":memory_id,
        "question_id":question_id,
        "task_id":task_id,
        "item_key":item_key
    }))


import ast

def extract_function(code_str, function_name):
    tree = ast.parse(code_str)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return ast.unparse(node)
    
    return None