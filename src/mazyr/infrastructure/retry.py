"""Shared tenacity retry policies for outbound adapters."""

import logging

import httpx
from qdrant_client.http.exceptions import ApiException, UnexpectedResponse
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mazyr.infrastructure.logger import get_logger

_log = get_logger("retry")

# Exponential backoff: 1s, 2s, 4s ... capped at 10s.
_WAIT = wait_exponential(multiplier=1, min=1, max=10)
_STOP = stop_after_attempt(3)

retry_llm = retry(
    retry=retry_if_exception_type((httpx.HTTPError, RuntimeError)),
    stop=_STOP,
    wait=_WAIT,
    reraise=True,
    before_sleep=before_sleep_log(_log, logging.WARNING),
)

retry_embedding = retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=_STOP,
    wait=_WAIT,
    reraise=True,
    before_sleep=before_sleep_log(_log, logging.WARNING),
)

retry_qdrant = retry(
    retry=retry_if_exception_type((UnexpectedResponse, ApiException)),
    stop=_STOP,
    wait=_WAIT,
    reraise=True,
    before_sleep=before_sleep_log(_log, logging.WARNING),
)

retry_telegram = retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=_STOP,
    wait=_WAIT,
    reraise=True,
    before_sleep=before_sleep_log(_log, logging.WARNING),
)

retry_github = retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=_STOP,
    wait=_WAIT,
    reraise=True,
    before_sleep=before_sleep_log(_log, logging.WARNING),
)

retry_api_call = retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=_STOP,
    wait=_WAIT,
    reraise=True,
    before_sleep=before_sleep_log(_log, logging.WARNING),
)
