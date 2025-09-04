# -*- coding: utf-8 -*-
"""
priority_executor.py
--------------------
موتور اجرای تسک‌ها با «اولویت»، «Aging (ارتقای تدریجی)»، «قفل‌های حوزه‌ای (ordering_scope)» و «ورکرهای موازی».

تفاوت کلیدی این نسخه:
- به‌جای بازهٔ ثابت 1..10، لیستِ اولویت‌ها را از config.json می‌خواند: executor.priority_levels
  * پیش‌فرض config: [0, 1, 2]  (۰ = بالاترین اولویت)
- صف‌ها دقیقاً بر اساس همین لیست ساخته می‌شوند (مثلاً ۳ صف برای [0,1,2]).
- Aging بر مبنای اندیسِ اولویت در لیست اجرا می‌شود (هر بار یک پله به سمت اندیس کمتر).
- پارامترهای اصلی (max_workers/queue_maxsize/...) از config.json خوانده می‌شوند (هات‌ریلُد-فرندلی).

کلیدهای مرتبط در config.json:
-----------------------------
executor.max_workers     : تعداد ورکرها (پیش‌فرض 4)
executor.priority_levels : لیست سطوح اولویت (پیش‌فرض [0,1,2]؛ ۰ = بالاترین)
executor.queue_maxsize   : حداکثر اندازهٔ صف (پیش‌فرض 100)

کلیدهای اختیاری (اگر نبودند، پیش‌فرض امن استفاده می‌شود):
executor.reserved_low_slots   : تعداد ورکر رزرو برای Low (پیش‌فرض 1)
executor.aging_step_seconds   : بازهٔ اجرای Aging (ثانیه) (پیش‌فرض 5)
executor.aging_step_amount    : پلهٔ ارتقا در هر چرخهٔ Aging (پیش‌فرض 1)
executor.idle_sleep           : خواب کوتاه ورکر در بی‌کاری (ثانیه) (پیش‌فرض 0.05)
executor.max_exec_ms_default  : حداکثر زمان اجرای تسک در صورت نبود max_exec_ms در هدر (میلی‌ثانیه) (پیش‌فرض 3000)

قراردادها:
- priority هر تسک باید یکی از مقادیر موجود در executor.priority_levels باشد؛ اگر نباشد، نرمال‌سازی می‌شود
  (نزدیک‌ترین مقدار موجود در لیست انتخاب می‌گردد).
- ordering_scope اگر تعیین شود، برای همان scope قفل می‌گذاریم تا نظم حفظ شود (تسک‌های هم‌دامنه هم‌زمان اجرا نشوند).
- TTL/Deadline قبل از اجرا بررسی می‌شود؛ در صورت انقضا، پاسخ "expired" بازگردانده می‌شود.

وابستگی‌ها: فقط استاندارد پایتون + config_manager
"""

from __future__ import annotations                     # ✔ تایپ‌هینت مدرن
import time                                            # ✔ زمان/خواب
import threading                                       # ✔ تردها و قفل‌ها
from collections import deque, defaultdict             # ✔ صف و دیکشنری پیش‌فرض‌ساز
from dataclasses import dataclass, field               # ✔ تعریف ساختار دادهٔ تسک
from typing import Any, Callable, Dict, Optional, Tuple, List  # ✔ تایپ‌ها
from datetime import datetime, timezone                # ✔ مهر زمان ISO
import bisect                                          # ✔ برای نرمال‌سازی عدد اولویت
import logging                                         # ✔ لاگ استاندارد
from config_manager import cfg                         # ✔ خواندن تنظیمات از config.json (هات‌ریلُد)

# ------------------------------------------------------------------------------
# ساختار دادهٔ «تسک فرمان» (ورودی موتور)
# ------------------------------------------------------------------------------
@dataclass
class CommandTask:
    """
    ساختار داده‌ی یک تسک فرمان.
    """
    corr_id: str                         # شناسهٔ پیگیری (Correlation Id)
    client_id: str                       # شناسهٔ کلاینتِ هدف (خود ما)
    priority: int                        # سطح اولویت (عضوی از executor.priority_levels)
    headers: Dict[str, Any]              # هدرهای ورودی پیام (می‌تواند max_exec_ms داشته باشد)
    body: Dict[str, Any]                 # بدنهٔ فرمان (class, method, args, ...)
    ordering_scope: Optional[str] = None # کلید حوزه (مثلاً per-symbol:EURUSD)
    ttl_ms: Optional[int] = None         # TTL برحسب میلی‌ثانیه (اختیاری)
    deadline_ts: Optional[float] = None  # یونیکس‌تایم (ثانیه) برای ددلاین مطلق (اختیاری)
    received_ts: float = field(default_factory=lambda: time.time())  # زمان دریافت پیام (ثانیه)
    last_aged_ts: float = field(default_factory=lambda: time.time()) # آخرین بار اعمال Aging
    extra: Dict[str, Any] = field(default_factory=dict)              # داده‌های اضافهٔ اختیاری

# ------------------------------------------------------------------------------
# کلاس موتور اولویت‌دار
# ------------------------------------------------------------------------------
class PriorityExecutor:
    """
    موتور اجرای اولویت‌دار با Aging و قفل‌های دامنه‌ای.
    تنظیمات از config.json خوانده می‌شود (هات‌ریلُد در نقاط حساس).
    """

    # ------------------------------- سازنده -------------------------------
    def __init__(
        self,
        *,
        execute_func: Optional[Callable[[CommandTask], Tuple[str, Dict[str, Any]]]] = None,  # تابع اجرایی بیرونی
        reply_callback: Optional[Callable[[CommandTask, str, Dict[str, Any]], None]] = None, # تابع ارسال پاسخ
        logger: Optional[logging.Logger] = None,                                             # لاگر اختیاری
    ):
        # ✔ لاگر: اگر پاس داده نشود، یک لاگر با نام کلاس برمی‌داریم
        self._log = logger or logging.getLogger(self.__class__.__name__)

        # ✔ توابع تزریق‌شونده (باید از بیرون داده شوند)
        self.execute_func = execute_func
        self.reply_callback = reply_callback

        # ✔ خواندن تنظیمات فعلی از config.json
        self._refresh_conf()

        # ✔ ساخت صف‌ها بر اساس لیستِ اولویت‌ها (برای هر سطح، یک deque)
        self.queues: Dict[int, deque] = {p: deque() for p in self.priority_levels}

        # ✔ قفل سراسری برای دسترسی به صف‌ها
        self.q_lock = threading.RLock()

        # ✔ قفل‌های دامنه‌ای (ordering_scope → Lock)
        self.scope_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)

        # ✔ کنترل تردها
        self._stop_event = threading.Event()
        self._aging_thread: Optional[threading.Thread] = None
        self._worker_threads: List[threading.Thread] = []

        # ✔ شمارندهٔ داخلی (برای دیباگ)
        self._seq = 0

    # --------------------------- خواندن/هات‌ریلُد کانفیگ ---------------------------
    def _refresh_conf(self) -> None:
        """
        خواندن تنظیمات از config.json (هات‌ریلُد-فرندلی).
        اگر کلیدی موجود نباشد، مقدار پیش‌فرض امن گذاشته می‌شود.
        """
        c = cfg()                                     # سینگلتون پیکربندی
        ec = c.get("executor", {}) or {}

        # لیست سطوح اولویت (مثلاً [0,1,2] یا [0,1,2,3,4])
        self.priority_levels: List[int] = list(ec.get("priority_levels", [0, 1, 2]))
        # مرتب‌سازی مطمئن (کوچک‌تر = اولویت بالاتر)
        self.priority_levels.sort()

        # تعداد ورکرها
        self.max_workers: int = int(ec.get("max_workers", 4))

        # حداکثر اندازهٔ صف (در این پیاده‌سازی به صورت soft-limit استفاده می‌شود)
        self.queue_maxsize: int = int(ec.get("queue_maxsize", 100))

        # پارامترهای اختیاری (اگر در config نبودند، پیش‌فرض امن داریم)
        self.reserved_low_slots: int   = int(ec.get("reserved_low_slots", 1))
        self.aging_step_seconds: int   = int(ec.get("aging_step_seconds", 5))
        self.aging_step_amount: int    = int(ec.get("aging_step_amount", 1))
        self.idle_sleep: float         = float(ec.get("idle_sleep", 0.05))
        self.max_exec_ms_default: int  = int(ec.get("max_exec_ms_default", 3000))

        # محاسبهٔ مجموعهٔ Low برای رزرو ورکرها:
        # تعریف: «نیمهٔ پایینِ لیست اولویت‌ها» (اندیس بزرگ‌تر = اولویت پایین‌تر)
        # مثال: [0,1,2,3] → Low = {2,3}  ،  [0,1,2] → Low = {1,2}
        half = max(1, len(self.priority_levels) // 2)
        self.low_levels = set(self.priority_levels[-half:])

        # ایجاد نگاشت «اولویت → اندیس» برای aging (کمک می‌کند یک پله جلو/عقب برویم)
        self._prio_to_index: Dict[int, int] = {p: i for i, p in enumerate(self.priority_levels)}

        # رشته‌های لاگ برای آگاهی
        self._log.info(
            "Executor config refreshed: priorities=%s, workers=%d, reserved_low=%d, aging=%ds(+%d), idle=%.2fs",
            self.priority_levels, self.max_workers, self.reserved_low_slots,
            self.aging_step_seconds, self.aging_step_amount, self.idle_sleep
        )

    # ------------------------------- توابع کمکی -------------------------------
    def _now(self) -> float:
        """زمان یونیکس (ثانیه) برای محاسبات داخلی."""
        return time.time()

    def _utc_iso(self) -> str:
        """زمان فعلی به ISO8601 در UTC (برای متادیتاها)."""
        return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    def _nearest_priority(self, p: int) -> int:
        """
        نرمال‌سازی «عدد اولویت» به نزدیک‌ترین مقدار موجود در priority_levels.
        اگر p دقیقاً در لیست نباشد، نزدیک‌ترین عضو انتخاب می‌شود.
        """
        levels = self.priority_levels
        # یافتن محل درج با bisect
        i = bisect.bisect_left(levels, p)
        if i == 0:
            return levels[0]
        if i == len(levels):
            return levels[-1]
        # انتخاب نزدیک‌ترین
        before, after = levels[i-1], levels[i]
        return before if abs(p - before) <= abs(after - p) else after

    def _higher_priority(self, p: int) -> int:
        """
        یک پله «بهتر» (اولویت بالاتر) نسبت به p برمی‌گرداند.
        در صورت رسیدن به بالاترین، همان p را می‌دهد.
        """
        idx = self._prio_to_index.get(p, 0)
        new_idx = max(0, idx - self.aging_step_amount)
        return self.priority_levels[new_idx]

    # ------------------------------- API عمومی -------------------------------
    def start(self) -> None:
        """
        استارت Aging و ورکرها. (ایمن در برابر استارت دوباره)
        """
        if self._aging_thread and self._aging_thread.is_alive():
            return

        # هات‌ریلُد کانفیگ در لحظهٔ استارت (برای زمان اجرا)
        self._refresh_conf()

        self._stop_event.clear()

        # ترد Aging
        self._aging_thread = threading.Thread(target=self._aging_loop, name="priority-aging", daemon=True)
        self._aging_thread.start()

        # ساخت/استارت ورکرها:
        # ابتدا reserved_low_slots ورکر برای Low
        for i in range(min(self.reserved_low_slots, self.max_workers)):
            t = threading.Thread(target=self._worker_loop, args=(True, i), name=f"worker-low-{i}", daemon=True)
            t.start()
            self._worker_threads.append(t)

        # بقیه ورکرها High→Low
        for i in range(len(self._worker_threads), self.max_workers):
            t = threading.Thread(target=self._worker_loop, args=(False, i), name=f"worker-hilo-{i}", daemon=True)
            t.start()
            self._worker_threads.append(t)

        self._log.info(
            "PriorityExecutor started (workers=%d, reserved_low=%d, levels=%s)",
            self.max_workers, self.reserved_low_slots, self.priority_levels
        )

    def stop(self, timeout: float = 2.0) -> None:
        """
        توقف امن: ترد Aging و ورکرها را متوقف می‌کند.
        """
        self._stop_event.set()
        for t in self._worker_threads:
            t.join(timeout=timeout)
        if self._aging_thread:
            self._aging_thread.join(timeout=timeout)
        self._log.info("PriorityExecutor stopped.")

    def submit(self, task: CommandTask) -> None:
        """
        افزودن یک تسک به صف مناسب (بر اساس priority).
        - priority اگر در لیست نبود، به نزدیک‌ترین مقدار نرمال می‌شود.
        - ظرفیت صف به صورت soft-limit است (در صورت نیاز می‌توانید آسان اضافه کنید).
        """
        # هات‌ریلُد احتمالی (اگر در حین اجرا config تغییر کرده باشد)
        self._refresh_conf()

        # نرمال‌سازی اولویت به نزدیک‌ترین مقدار مجاز
        p = self._nearest_priority(int(task.priority))
        task.priority = p

        with self.q_lock:
            # کنترل ظرفیت نرم: اگر خیلی بزرگ شد، همچنان قبول می‌کنیم اما قابل مانیتور است
            if self.queue_maxsize and sum(len(q) for q in self.queues.values()) >= self.queue_maxsize:
                self._log.warning("Queue soft-limit reached (size≈%d)", self.queue_maxsize)
            self.queues[p].append(task)
            self._seq += 1
            self._log.debug("Task queued", extra={"p": p, "corr_id": task.corr_id, "scope": task.ordering_scope})

    # ------------------------------- Aging -------------------------------
    def _aging_loop(self) -> None:
        """
        هر aging_step_seconds، پیام‌های مانده را یک «پله» به سمت اولویت بهتر ارتقا می‌دهد.
        معیار: از آخرین ارتقای خود (last_aged_ts) حداقل aging_step_seconds گذشته باشد.
        """
        while not self._stop_event.is_set():
            time.sleep(max(1, int(self.aging_step_seconds)))
            now = self._now()

            try:
                moved = 0
                with self.q_lock:
                    # از «پایین‌ترین اولویت‌ها» به سمت بالا حرکت می‌کنیم تا ارتقا درست انجام شود
                    for p in reversed(self.priority_levels):
                        q = self.queues[p]
                        for _ in range(len(q)):  # فقط اندازهٔ فعلی؛ از حلقهٔ بی‌نهایت جلوگیری
                            task = q.popleft()
                            # اگر به زمان Aging رسیده باشد
                            if (now - task.last_aged_ts) >= self.aging_step_seconds:
                                new_p = self._higher_priority(task.priority)
                                if new_p != task.priority:
                                    task.priority = new_p
                                    task.last_aged_ts = now
                                    self.queues[new_p].append(task)
                                    moved += 1
                                else:
                                    # در بالاترین اولویت است؛ همان صف بماند
                                    q.append(task)
                            else:
                                # هنوز نوبت Aging این تسک نرسیده
                                q.append(task)
                if moved:
                    self._log.debug("Aging moved tasks", extra={"count": moved})
            except Exception as e:
                self._log.warning("Aging loop error: %s", str(e))

    # ------------------------ انتخاب و اجرای تسک ------------------------
    def _pick_next_task(self, reserved_low: bool) -> Optional[CommandTask]:
        """
        انتخاب تسک بعدی:
        - اگر reserved_low=True: ابتدا بین «سطوح Low» می‌گردد؛ اگر نبود → کل سطوح از بالا به پایین.
        - اگر reserved_low=False: کل سطوح از بالا (بهترین) تا پایین.
        """
        with self.q_lock:
            if reserved_low:
                # ابتدا Lowها (نیمهٔ پایین)
                for p in self.priority_levels:
                    if p in self.low_levels and self.queues[p]:
                        return self.queues[p].popleft()
                # برای جلوگیری از بیکاری، از بالا به پایین
                for p in self.priority_levels:
                    if self.queues[p]:
                        return self.queues[p].popleft()
            else:
                # از بالاترین به پایین‌ترین
                for p in self.priority_levels:
                    if self.queues[p]:
                        return self.queues[p].popleft()
        return None

    def _run_with_timeout(self, task: CommandTask, max_exec_ms: int) -> Tuple[str, Dict[str, Any]]:
        """
        اجرای تابع بیرونی با محدودیت زمان.
        توجه: در پایتون ترد را واقعاً kill نمی‌کنیم؛ اگر دیرتر شد، TimeoutError می‌دهیم.
        """
        if self.execute_func is None:
            raise RuntimeError("execute_func تزریق نشده است.")

        result_holder: Dict[str, Any] = {"status": "error", "result": {}}
        finished = threading.Event()

        def runner():
            try:
                st, rs = self.execute_func(task)   # تابع باید (status, dict) بدهد
                result_holder["status"] = st
                result_holder["result"] = rs
            except Exception as e:
                result_holder["status"] = "error"
                result_holder["result"] = {"reason": str(e)}
            finally:
                finished.set()

        th = threading.Thread(target=runner, daemon=True)
        th.start()
        ok = finished.wait(timeout=max_exec_ms / 1000.0)
        if not ok:
            # ترد runner ممکن است ادامه دهد؛ ما پاسخ timeout می‌دهیم
            raise TimeoutError("execution timeout")
        return result_holder["status"], result_holder["result"]

    def _reply_status(self, task: CommandTask, status: str, result: Dict[str, Any]) -> None:
        """
        فراخوانی کال‌بک پاسخ (مثلاً ارسال به Kafka) با corr_id و متادیتاها.
        """
        try:
            if self.reply_callback is None:
                self._log.warning("reply_callback not set; dropping reply", extra={"corr_id": task.corr_id})
                return
            self.reply_callback(task, status, result)
        except Exception as e:
            self._log.warning("reply_callback failed: %s", str(e), extra={"corr_id": task.corr_id})

    def _worker_loop(self, reserved_low: bool, index: int) -> None:
        """
        حلقهٔ اصلی هر ورکر:
        - reserved_low=True → ابتدا Lowها؛ اگر نبود، از بالا به پایین برای جلوگیری از بیکاری.
        - reserved_low=False → همیشه از بالا به پایین (بهترین → پایین‌ترین).
        """
        name = threading.current_thread().name
        self._log.info("Worker started", extra={"name": name, "reserved_low": reserved_low})

        while not self._stop_event.is_set():
            # هات‌ریلُد سبکِ کانفیگ (در حلقهٔ ورکر)
            self._refresh_conf()

            task = self._pick_next_task(reserved_low=reserved_low)
            if task is None:
                time.sleep(self.idle_sleep)
                continue

            # اعتبارسنجی TTL/Deadline قبل از اجرا
            now = self._now()
            expired = False

            if task.deadline_ts is not None and now > task.deadline_ts:
                expired = True

            if task.ttl_ms is not None:
                if (now - task.received_ts) * 1000.0 > float(task.ttl_ms):
                    expired = True

            if expired:
                self._reply_status(task, status="expired", result={"reason": "deadline/ttl exceeded"})
                continue

            # قفل حوزه‌ای در صورت وجود ordering_scope
            lock_acquired = False
            scope_lock = None
            if task.ordering_scope:
                scope_lock = self.scope_locks[task.ordering_scope]
                # تلاش کوتاه برای جلوگیری از بن‌بست
                lock_acquired = scope_lock.acquire(timeout=0.1)
                if not lock_acquired:
                    # اگر قفل نشد، تسک را جلوی صف خودش برگردان و کمی بخواب
                    with self.q_lock:
                        self.queues[task.priority].appendleft(task)
                    time.sleep(self.idle_sleep)
                    continue

            # اجرای واقعی با حد زمان
            start = self._now()
            status = "error"
            result: Dict[str, Any] = {}
            try:
                max_exec_ms = int(task.headers.get("max_exec_ms", self.max_exec_ms_default))
                status, result = self._run_with_timeout(task, max_exec_ms)
            except TimeoutError:
                status = "timeout"
                result = {"reason": "max_exec_ms exceeded"}
            except Exception as e:
                status = "error"
                result = {"reason": str(e)}
            finally:
                if lock_acquired and scope_lock:
                    try:
                        scope_lock.release()
                    except Exception:
                        pass

            elapsed_ms = int((self._now() - start) * 1000.0)
            # افزودن متادیتا به نتیجه
            meta = {"elapsed_ms": elapsed_ms, "effective_priority": task.priority, "ts": self._utc_iso()}
            if isinstance(result, dict):
                result.setdefault("meta", {}).update(meta)
            else:
                result = {"result": result, "meta": meta}

            # ارسال پاسخ
            self._reply_status(task, status=status, result=result)
