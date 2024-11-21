from .base import BaseServer
from .batchtask_executor import BatchTaskExecutor
from .code_executor import CodeExecutor
from .gpt import GPTServer
from .llama import LLaMAServer

from typing import Dict, Type

SERVER:Dict[str, Type[BaseServer]] = dict()

for server in (
    CodeExecutor,
    BatchTaskExecutor,
    GPTServer,
    LLaMAServer,
):
    SERVER[server.SERVER_KEY] = server