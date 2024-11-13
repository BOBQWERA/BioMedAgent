import json
import time
import redis

from uuid import uuid4
from typing import Any

class BaseServer:
    CENTER_KEY_PREFIX = "biomedagent:server_center"
    HEARTBEAT_KEY = "biomedagent:server_heartbeat"
    DEAD_POOL = "biomedagent:server_dead"
    SERVER_KEY = "base"
    SLEEP_TIME = 1
    def __init__(self) -> None:
        self.r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.center = f"{self.CENTER_KEY_PREFIX}:{self.SERVER_KEY}"
        self.id = str(uuid4())

        self._regester()

    def _regester(self) -> None:
        self.r.hset(self.center,self.id,json.dumps({
            "id":self.id,
            "status":"wait", #status: ['wait', 'run']
        }))
        self.r.hset(self.HEARTBEAT_KEY, self.id, int(time.time()))

    def _change_status(self, status):
        info = self.r.hget(self.center,self.id)
        info = json.loads(info)
        info["status"] = status
        self.r.hset(self.center,self.id,json.dumps(info))

    def start_task(self):
        self._change_status('run')

    def finish_task(self):
        self._change_status('wait')

    def check_alive(self):
        return not bool(
            self.r.hget(self.DEAD_POOL, self.id)
        )

    def get_task(self):
        return False , None
    
    def execute(self, data):
        ...

    def heartbeat(self) -> None:
        self.r.hset(self.HEARTBEAT_KEY, self.id, int(time.time()))

    def on_error(self, e:Exception, data):
        raise e

    def run(self):
        while True:
            if not self.check_alive():
                break
            self.heartbeat()
            ok, data = self.get_task()
            if not ok:
                time.sleep(self.SLEEP_TIME)
                continue
            self.start_task()
            try:
                self.execute(data)
            except Exception as e:
                self.on_error(e, data)
            self.finish_task()