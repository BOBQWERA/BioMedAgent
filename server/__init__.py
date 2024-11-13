from .base import BaseServer
from .batchtask_executor import BatchTaskExecutor
from .code_executor import CodeExecutor
from .gpt import GPTServer
from .llama import LLaMAServer
from .memory_server import MemoryServer

from typing import Dict, Type

SERVER:Dict[str, Type[BaseServer]] = dict()

for server in (
    CodeExecutor,
    BatchTaskExecutor,
    GPTServer,
    LLaMAServer,
    MemoryServer,
):
    SERVER[server.SERVER_KEY] = server