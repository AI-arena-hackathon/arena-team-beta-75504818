import os
import sqlite3
import time
import logging
import threading
from contextlib import contextmanager
from functools import wraps
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open
        self._lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        with self._lock:
            if self.state == "open":
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = "half-open"
                    logger.info("Circuit breaker entering half-open state")
                else:
                    raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            with self._lock:
                if self.state == "half-open":
                    self.state = "closed"
                    self.failure_count = 0
                    logger.info("Circuit breaker closed after successful call")
            return result
        except self.expected_exception as e:
            with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                    logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            raise

    def reset(self):
        with self._lock:
            self.failure_count = 0
            self.state = "closed"
            self.last_failure_time = None


class CircuitBreakerOpenError(Exception):
    pass


class RetryPolicy:
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 2.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple = (sqlite3.OperationalError, sqlite3.DatabaseError),
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        last_exception = None
        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)
            except self.retryable_exceptions as e:
                last_exception = e
                if attempt < self.max_attempts - 1:
                    delay = min(
                        self.base_delay * (self.exponential_base ** attempt),
                        self.max_delay,
                    )
                    if self.jitter:
                        import random
                        delay *= (0.5 + random.random())
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_attempts} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_attempts} attempts failed")
        raise last_exception


class DatabasePool:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_path = os.environ.get('DATABASE_PATH', '/data/seniorcare.db')
        self.pool_size = int(os.environ.get('DB_POOL_SIZE', '5'))
        self.timeout = float(os.environ.get('DB_TIMEOUT', '30.0'))
        self._pool = []
        self._pool_lock = threading.Lock()
        self._local = threading.local()
        self._init_pool()
        self._initialized = True

    def _init_pool(self):
        for _ in range(self.pool_size):
            conn = self._create_connection()
            self._pool.append(conn)

    def _create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-2000")
        return conn

    @contextmanager
    def get_connection(self):
        conn = getattr(self._local, 'connection', None)
        if conn is None:
            with self._pool_lock:
                if self._pool:
                    conn = self._pool.pop()
                else:
                    conn = self._create_connection()
            self._local.connection = conn

        try:
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            self._replace_connection(conn)
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise

    def _replace_connection(self, old_conn):
        try:
            old_conn.close()
        except sqlite3.Error:
            pass
        with self._pool_lock:
            if len(self._pool) < self.pool_size:
                self._pool.append(self._create_connection())

    def close_all(self):
        with self._pool_lock:
            for conn in self._pool:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self._pool.clear()


def get_db_pool() -> DatabasePool:
    return DatabasePool()


def with_retry(policy: Optional[RetryPolicy] = None):
    if policy is None:
        policy = RetryPolicy()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return policy.execute(func, *args, **kwargs)
        return wrapper
    return decorator


def with_circuit_breaker(breaker: Optional[CircuitBreaker] = None):
    if breaker is None:
        breaker = CircuitBreaker()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


default_retry_policy = RetryPolicy(
    max_attempts=3,
    base_delay=0.1,
    max_delay=2.0,
)

db_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
    expected_exception=sqlite3.Error,
)