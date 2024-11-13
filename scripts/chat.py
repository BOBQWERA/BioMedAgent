from copy import deepcopy

from scripts.llm import llmcall,llmresponse

class ChatSession:
    def __init__(self, model, temperature, config, messages=None) -> None:
        self.model = model
        self.temperature = temperature
        self.config = config
        self.messages = [] if messages is None else deepcopy(messages)
        self.__lock = False


    def copy(self):
        return ChatSession(
            self.model,
            self.temperature,
            self.config,
            self.messages
        )

    def set_system(self, system):
        self.messages.append({
            "role":"system",
            "content":system
        })
    
    async def chat(self,content):
        self.__lock = True
        self.messages.append({
            "role":"user",
            "content":content
        })
        uid = llmcall(
            self.model,
            self.temperature,
            self.messages,
            self.config
        )
        msg = await llmresponse(uid, self.config)
        self.messages.append({
            "role":"assistant",
            "content":msg
        })
        self.__lock = False
        return msg
    


if __name__ == "__main__":
    from uuid import uuid4
    from config import Config
    
    task_id = uuid4()
    config = Config.set_task(task_id)

    session = ChatSession(
        model="gpt-3.5-turbo",temperature=0.5,config=config
    )

    session.set_system(
        "ai"
    )

    import asyncio 
    asyncio.run(session.chat("今天怎么样"))
    
    import random

    questions = [f"{a} {b} {c} = ?" for a,b,c in zip(
        random.choices(range(1,100),k=5),random.choices("+-*/",k=5),random.choices(range(1,100),k=5)
    )]
    
    async def main():
        tasks = []
        for question in questions:
            session = ChatSession(
                model="gpt-3.5-turbo",temperature=0.5,config=config
            )
            session.set_system(
                "ai"
            )
            task = asyncio.create_task(session.chat(question))
            tasks.append(task)
        result = []
        for task in tasks:
            result.append(await task)
        return result

    result = asyncio.run(main())

    print(result)
    