# -*- coding: utf-8 -*-
import threading, queue, time, logging
from typing import Callable, Any, Tuple
from config_manager import cfg

Task = Tuple[int, int, Callable[[], Any]]  # (priority, seq_no, callable)

class PriorityExecutor:
    def __init__(self):
        c = cfg()
        excfg = c.get("executor", {})
        self.max_workers = int(excfg.get("max_workers", 4))
        self.queue_maxsize = int(excfg.get("queue_maxsize", 100))
        self._q: "queue.PriorityQueue[Task]" = queue.PriorityQueue(self.queue_maxsize)
        self._seq = 0
        self._workers = []
        self._stop = threading.Event()
        self._log = logging.getLogger(self.__class__.__name__)

        for i in range(self.max_workers):
            t = threading.Thread(target=self._worker_loop, name=f"Worker-{i}", daemon=True)
            t.start()
            self._workers.append(t)

    def submit(self, priority: int, fn: Callable[[], Any]) -> None:
        if priority is None:
            priority = 1
        self._seq += 1
        self._q.put((priority, self._seq, fn))

    def _worker_loop(self):
        while not self._stop.is_set():
            try:
                prio, _, fn = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                fn()
            except Exception as e:
                self._log.exception("Task failed: %s", e)
            finally:
                self._q.task_done()

    def stop(self, wait=True):
        self._stop.set()
        if wait:
            for t in self._workers:
                t.join(timeout=1.0)
