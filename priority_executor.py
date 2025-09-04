# -*- coding: utf-8 -*-
"""
priority_executor.py
--------------------
مدیر صف‌های اولویت‌دار داخل کلاینت + Aging + قفل‌های حوزه‌ای + ورکرهای موازی.

نحوه‌ی کار:
- submit() را با اطلاعات فرمان (headers+body) صدا بزن؛ ماژول پیام را به یکی از 10 صف 1..10 اضافه می‌کند.
- یک ترد Aging هر 5 ثانیه پیام‌های قدیمی را یک پله به اولویت بالاتر (عدد کوچک‌تر) منتقل می‌کند.
- ورکرها به ترتیب از صف‌های مهم‌تر برمی‌دارند و اجرا می‌کنند.
- اگر ordering_scope (مثل per-symbol:EURUSD) تعیین شده باشد، برای همان scope قفل می‌گذاریم تا نظم حفظ شود.
- یک ورکر به‌صورت رزرو‌شده کم‌اهمیت‌ها (6..10) را سرویس می‌دهد تا هرگز قفل کامل نشوند.

وابستگی‌ها: استاندارد پایتون. نیاز به کافکا ندارد؛ فقط تابع‌های اجرایی/پاسخ‌دهی را از بیرون می‌گیرد.
"""

import time
import threading
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple, List
from datetime import datetime, timedelta, timezone

# ---- انواع ساده برای خوانایی کد ----

@dataclass
class CommandTask:
    """
    ساختار داده‌ی یک تسک فرمان.
    """
    corr_id: str                         # شماره پیگیری (هم‌بستگی)
    client_id: str                       # شناسه‌ی کلاینتِ هدف (خود ما)
    priority: int                        # اولویت اولیه 1..10 (1 فوری‌ترین)
    headers: Dict[str, str]              # هدرهای ورودی پیام
    body: Dict[str, Any]                 # بدنه‌ی فرمان (class, method, args, ...)
    ordering_scope: Optional[str] = None # کلید حوزه (مثلاً per-symbol:EURUSD)
    ttl_ms: Optional[int] = None         # TTL برحسب میلی‌ثانیه (اختیاری)
    deadline_ts: Optional[float] = None  # یونیکس‌تایم ثانیه (اختیاری)
    received_ts: float = field(default_factory=lambda: time.time())  # زمان دریافت پیام (ثانیه)
    last_aged_ts: float = field(default_factory=lambda: time.time()) # آخرین بار که Aging اعمال شد
    # اختیاری برای ارسال پاسخ
    extra: Dict[str, Any] = field(default_factory=dict)


class PriorityExecutor:
    """
    موتور اجرای اولویت‌دار با Aging و قفل‌های درون‌حوزه‌ای.
    """

    def __init__(
        self,
        *,
        workers: int = 4,                 # تعداد کل ورکرها
        reserved_low_slots: int = 1,      # چند ورکر مخصوص 6..10 رزرو شوند
        aging_step_seconds: int = 5,      # هر چند ثانیه یک پله Aging
        # اگر بخواهیم Aging سریع‌تر/آهسته‌تر باشد
        aging_step_amount: int = 1,       # هر گام چند پله ارتقا (معمولاً 1)
        # محدوده‌ی Low برای رزرو
        low_range: Tuple[int, int] = (6, 10),
        # مهلت اجرای پیش‌فرض اگر max_exec_ms در پیام نبود
        max_exec_ms_default: int = 3000,
        # توابع تزریق‌شونده:
        execute_func: Optional[Callable[[CommandTask], Tuple[str, Dict[str, Any]]]] = None,
        # باید تابعی باشد که پاسخ را ارسال کند (کافکا یا هرچیز دیگر)
        reply_callback: Optional[Callable[[CommandTask, str, Dict[str, Any]], None]] = None,
        # تایمر خواب کوتاه بین تلاش‌ها
        idle_sleep: float = 0.05,
        logger: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
    ):
        # لاگر ساده: logger(level, message, extra)
        self.log = logger or self._fallback_log

        # پارامترها
        self.workers = max(1, workers)
        self.reserved_low_slots = max(0, min(reserved_low_slots, self.workers))
        self.aging_step_seconds = max(1, aging_step_seconds)
        self.aging_step_amount = max(1, aging_step_amount)
        self.low_range = low_range
        self.max_exec_ms_default = max_exec_ms_default
        self.idle_sleep = idle_sleep

        # هوک‌های بیرونی
        self.execute_func = execute_func
        self.reply_callback = reply_callback

        # صف‌ها: 10 صف از 1..10 (1 بالاترین اولویت)
        self.queues: Dict[int, deque] = {p: deque() for p in range(1, 11)}

        # قفل سراسری برای دسترسی به صف‌ها
        self.q_lock = threading.RLock()

        # قفل‌های درون‌حوزه‌ای: هر scope یک Lock
        self.scope_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)

        # کنترل تردها
        self._stop_event = threading.Event()
        self._aging_thread: Optional[threading.Thread] = None
        self._worker_threads: List[threading.Thread] = []

        # شمارنده‌ها
        self._seq = 0  # فقط برای دیباگ/لاگ

    # --------------- ابزارهای داخلی ---------------

    def _fallback_log(self, level: str, msg: str, extra: Dict[str, Any] = None):
        # لاگ سادهٔ چاپی
        print(f"[{level.upper()}] {msg} {extra or ''}")

    def _now(self) -> float:
        return time.time()

    def _utc_iso(self) -> str:
        return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    def _within_low_range(self, p: int) -> bool:
        lo, hi = self.low_range
        return lo <= p <= hi

    # --------------- API عمومی ---------------

    def start(self):
        """
        استارت Aging و ورکرها.
        """
        if self._aging_thread and self._aging_thread.is_alive():
            return

        self._stop_event.clear()
        # ترد Aging
        self._aging_thread = threading.Thread(target=self._aging_loop, name="priority-aging", daemon=True)
        self._aging_thread.start()

        # تردهای ورکر:
        # اول reserved_low_slots تا worker را برای Low رزرو می‌کنیم
        for i in range(self.reserved_low_slots):
            t = threading.Thread(target=self._worker_loop, args=(True, i), name=f"worker-low-{i}", daemon=True)
            t.start()
            self._worker_threads.append(t)
        # بقیه High→Low
        for i in range(self.reserved_low_slots, self.workers):
            t = threading.Thread(target=self._worker_loop, args=(False, i), name=f"worker-hilo-{i}", daemon=True)
            t.start()
            self._worker_threads.append(t)

        self.log("info", "PriorityExecutor started", {"workers": self.workers, "reserved_low": self.reserved_low_slots})

    def stop(self, timeout: float = 2.0):
        """
        توقف امن: ترد Aging و ورکرها را متوقف می‌کند.
        """
        self._stop_event.set()
        # تردها بطور طبیعی پایان می‌یابند
        for t in self._worker_threads:
            t.join(timeout=timeout)
        if self._aging_thread:
            self._aging_thread.join(timeout=timeout)

    def submit(self, task: CommandTask):
        """
        افزودن یک تسک به صف مناسب (بر اساس priority).
        """
        # اولویت را داخل بازه‌ی 1..10 نگه می‌داریم
        p = max(1, min(10, int(task.priority or 5)))
        task.priority = p  # normalize

        with self.q_lock:
            self.queues[p].append(task)
            self._seq += 1
            self.log("debug", "task queued", {"p": p, "corr_id": task.corr_id, "scope": task.ordering_scope})

    # --------------- Aging ---------------

    def _aging_loop(self):
        """
        هر aging_step_seconds، پیام‌های مانده را یک «پله» ارتقا می‌دهد (مثلاً از 8 به 7).
        برای کارایی، ما فقط پیام‌هایی را که حداقل aging_step_seconds از last_aged_ts‌شان گذشته، جابجا می‌کنیم.
        """
        while not self._stop_event.is_set():
            time.sleep(self.aging_step_seconds)
            now = self._now()

            try:
                moved_count = 0
                with self.q_lock:
                    # از پایین به بالا حرکت می‌کنیم (10..2) و هرکدام را در صورت نیاز به پله‌ی بالاتر می‌بریم
                    for p in range(10, 1, -1):
                        q = self.queues[p]
                        # برای جلوگیری از چرخشِ بی‌پایان، فقط اندازه‌ی فعلی صف را بازرسی می‌کنیم
                        for _ in range(len(q)):
                            task = q.popleft()
                            # اگر به‌اندازه‌ی کافی عمر کرده، و هنوز جا برای ارتقا هست
                            if (now - task.last_aged_ts) >= self.aging_step_seconds:
                                # چند پله ارتقا (معمولاً 1)
                                new_p = max(1, task.priority - self.aging_step_amount)
                                # اگر ارتقا اتفاق افتاد
                                if new_p < task.priority:
                                    task.priority = new_p
                                    task.last_aged_ts = now
                                    self.queues[new_p].append(task)
                                    moved_count += 1
                                else:
                                    # ارتقا نداشت، سرجایش بماند
                                    q.append(task)
                            else:
                                # هنوز نوبت Aging این تسک نرسیده، همان صف خودش
                                q.append(task)
                if moved_count:
                    self.log("debug", "aging moved tasks", {"count": moved_count})
            except Exception as e:
                self.log("warn", "aging loop error", {"error": str(e)})

    # --------------- انتخاب و اجرای تسک ---------------

    def _worker_loop(self, reserved_low: bool, index: int):
        """
        حلقهٔ اصلی هر ورکر:
        - اگر reserved_low=True → ابتدا 6..10 را اسکن می‌کند؛ اگر نبود، برای جلوگیری از بیکاری به High→Low برمی‌گردد.
        - اگر reserved_low=False → High→Low (1..10) را اسکن می‌کند.
        """
        name = threading.current_thread().name
        self.log("info", "worker started", {"name": name, "reserved_low": reserved_low})
        while not self._stop_event.is_set():
            task = self._pick_next_task(reserved_low=reserved_low)
            if task is None:
                time.sleep(self.idle_sleep)
                continue

            # اعتبارسنجی TTL/Deadline قبل از اجرا
            now = self._now()
            expired = False

            # deadline_ts اگر تعیین شده بود و گذشته باشد → منقضی
            if task.deadline_ts is not None and now > task.deadline_ts:
                expired = True

            # ttl_ms اگر تعیین شده بود و از زمان دریافت گذشته باشد → منقضی
            if task.ttl_ms is not None:
                if (now - task.received_ts) * 1000.0 > float(task.ttl_ms):
                    expired = True

            if expired:
                self._reply_status(task, status="expired", result={"reason": "deadline/ttl exceeded"})
                continue

            # قفل حوزه (اگر scope تعریف شده بود)
            lock_acquired = False
            scope_lock = None
            if task.ordering_scope:
                scope_lock = self.scope_locks[task.ordering_scope]
                lock_acquired = scope_lock.acquire(timeout=0.1)  # تلاش کوتاه برای جلوگیری از بن‌بست
                if not lock_acquired:
                    # اگر قفل نبود، تسک را به همان صف خودش برگردانیم تا بعداً دوباره تلاش شود
                    with self.q_lock:
                        self.queues[task.priority].appendleft(task)  # اول صف تا زودتر دوباره امتحان شود
                    time.sleep(self.idle_sleep)
                    continue

            # اجرای واقعی با حد زمان
            start = self._now()
            status = "error"
            result: Dict[str, Any] = {}
            try:
                # تعیین max_exec_ms مؤثر
                max_exec_ms = int(task.headers.get("max_exec_ms", self.max_exec_ms_default))
                # اجرای تابع بیرونی (باید از بیرون تزریق شده باشد)
                if self.execute_func is None:
                    raise RuntimeError("execute_func تزریق نشده است.")
                status, result = self._run_with_timeout(task, max_exec_ms)
            except TimeoutError:
                status = "timeout"
                result = {"reason": "max_exec_ms exceeded"}
            except Exception as e:
                status = "error"
                result = {"reason": str(e)}
            finally:
                # آزاد کردن قفل حوزه
                if lock_acquired and scope_lock:
                    try:
                        scope_lock.release()
                    except Exception:
                        pass

            elapsed_ms = int((self._now() - start) * 1000.0)
            # افزودن متادیتا
            result_meta = {"elapsed_ms": elapsed_ms, "effective_priority": task.priority}
            if isinstance(result, dict):
                result.setdefault("meta", {}).update(result_meta)
            else:
                result = {"result": result, "meta": result_meta}

            # پاسخ
            self._reply_status(task, status=status, result=result)

    def _pick_next_task(self, reserved_low: bool) -> Optional[CommandTask]:
        """
        انتخاب بعدی:
        - اگر reserved_low=True: ابتدا 6..10؛ اگر نبود → 1..10 برای جلوگیری از بیکاری
        - اگر reserved_low=False: 1..10
        """
        with self.q_lock:
            if reserved_low:
                # ابتدا low-range
                for p in range(self.low_range[0], self.low_range[1] + 1):
                    if self.queues[p]:
                        return self.queues[p].popleft()
                # اگر low نبود، از high→low برای جلوگیری از بیکاری
                for p in range(1, 11):
                    if self.queues[p]:
                        return self.queues[p].popleft()
            else:
                # high→low
                for p in range(1, 11):
                    if self.queues[p]:
                        return self.queues[p].popleft()
        return None

    def _run_with_timeout(self, task: CommandTask, max_exec_ms: int) -> Tuple[str, Dict[str, Any]]:
        """
        اجرای تابع بیرونی با محدودیت زمان. در پایتون ترد را «واقعاً» kill نمی‌کنیم،
        اما از طریق یک روال ساده، اگر دیرتر شد، TimeoutError می‌دهیم.
        """
        res_holder: Dict[str, Any] = {"status": "error", "result": {}}
        finished = threading.Event()

        def runner():
            try:
                st, rs = self.execute_func(task)  # تابع بیرونی باید (status, result_dict) برگرداند
                res_holder["status"] = st
                res_holder["result"] = rs
            except Exception as e:
                res_holder["status"] = "error"
                res_holder["result"] = {"reason": str(e)}
            finally:
                finished.set()

        th = threading.Thread(target=runner, daemon=True)
        th.start()
        ok = finished.wait(timeout=max_exec_ms / 1000.0)
        if not ok:
            # توجه: ترد runner همچنان ممکن است پشت‌صحنه ادامه دهد؛ پاسخ timeout می‌دهیم
            raise TimeoutError("execution timeout")
        return res_holder["status"], res_holder["result"]

    def _reply_status(self, task: CommandTask, status: str, result: Dict[str, Any]):
        """
        فراخوانی کال‌بک پاسخ (کافکا…) با corr_id/priority و ...
        """
        try:
            if self.reply_callback is None:
                self.log("warn", "reply_callback not set; dropping reply", {"corr_id": task.corr_id})
                return
            self.reply_callback(task, status, result)
        except Exception as e:
            self.log("warn", "reply_callback failed", {"error": str(e), "corr_id": task.corr_id})

