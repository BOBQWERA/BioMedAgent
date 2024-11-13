import asyncio
import os
import json
import requests
import time

from config import Config

from utils import gprint, generate_task_id

def handle_text(func):
    def inner(uid, config:Config):
        ok, msg = func(uid, config)
        if config.ECHO_INFO and ok:
            print(msg)
            gprint("="*30)
        if not config.SAVE_LOG or not ok: return ok, msg
        task_id = config.get_task()
        log_path = os.path.join(
            f"{config.LOG_DIR}",config.time_path
        )
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        with open(os.path.join(log_path,f"{task_id}.log"),"a",encoding="utf8") as f:
            f.write(f"{msg}\n{'='*30}\n")
        return ok, msg
    
    async def wait(uid, config:Config):
        ok = False
        while not ok:
            ok, msg = inner(uid, config)
            if not ok: await asyncio.sleep(config.LLM_CALL_WAITING_TIME)
        return msg

    return wait

def llmcall(model, temperature, messages, config:Config):
    uid = generate_task_id()
    data = {
        "task_id": uid,
        "messages": messages,
        "temperature": temperature,
        "model": model
    }

    r = config.get_redis_connect()
    r.lpush(config.REDIS_GPT_TASK_KEY, json.dumps(data))

    return uid

@handle_text
def llmresponse(uid:str, config:Config):
    r = config.get_redis_connect()
    result = r.hget(config.REDIS_GPT_RESULT_KEY, uid)
    if not result: return False, ""
    result = json.loads(result)
    return True, result["response"]

if __name__ == "__main__":
    from config import Config
    from uuid import uuid4
    import json
    import asyncio
    task_id = uuid4()
    config = Config.set_task(f"{task_id}")
    uid = llmcall(model="gpt-4-turbo",temperature=0.5,messages=[
        {
            "role":"system",
            "content":"you are a helpful ai"
        },
        {
            "role":"user",
            "content":"你好啊"
        }
    ],config=config)

    asyncio.run(llmresponse(uid, config))

    