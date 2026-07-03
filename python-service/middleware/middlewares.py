import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enable: bool = True, threshold: float = 1.0):
        super().__init__(app)
        self.enable = enable
        self.threshold = threshold

    async def dispatch(self, request: Request, call_next):
        if not self.enable:
            return await call_next(request)

        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time

        if process_time > self.threshold:
            logger.warning(
                "接口响应耗时 - 接口 %s 耗时: %.4f 秒",
                request.url.path,
                process_time,
            )

        return response
