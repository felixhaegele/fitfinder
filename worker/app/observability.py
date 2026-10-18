"""Error tracking with Sentry.

Call `init_sentry()` once at start-up from every entrypoint (the HTTP app in
`app/main.py`, and the queue consumer). Without `SENTRY_DSN` it does nothing,
so local dev, CI and tests never send events.

Privacy (GDPR / Swiss FADP): no default PII, no request bodies, no stack-frame
local variables (they would contain image arrays, DB URLs and signed URLs), and
`before_send` scrubs emails, JWTs, signed storage paths and query-string values
from every string in an event. The web app applies the same rules in
web/src/lib/sentry.ts.
"""

import os
import re
from typing import Any

import sentry_sdk
from sentry_sdk.types import Event, Hint

FILTERED = "[Filtered]"

# Request headers we keep; everything else (cookie, authorization, apikey, ...) is dropped.
SAFE_HEADERS = frozenset({"accept", "accept-language", "content-type", "user-agent"})

# Object keys whose values are never sent, wherever they appear in an event.
SENSITIVE_KEY = re.compile(
    r"cookie|authorization|password|passwd|secret|token|api[-_]?key|session|email|signature|dsn|db_url",
    re.IGNORECASE,
)

STRING_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]*)?"), "[jwt]"),
    (re.compile(r"(/storage/v1/object/sign/)[^?#\s\"']+"), rf"\g<1>{FILTERED}"),
    # Every query-string value; keeps the parameter names for debugging.
    (re.compile(r"([?&][^=&#\s\"'?]+=)[^&#\s\"']*"), rf"\g<1>{FILTERED}"),
    # Credentials in connection strings, e.g. postgresql://user:password@host
    (re.compile(r"(://[^:/\s]+:)[^@/\s]+@"), rf"\g<1>{FILTERED}@"),
)

MAX_DEPTH = 12


def scrub_string(value: str) -> str:
    for pattern, replacement in STRING_RULES:
        value = pattern.sub(replacement, value)
    return value


def _scrub(value: Any, depth: int) -> Any:
    if isinstance(value, str):
        return scrub_string(value)
    if depth > MAX_DEPTH:
        return value
    if isinstance(value, dict):
        return {
            key: FILTERED
            if isinstance(key, str) and SENSITIVE_KEY.search(key)
            else _scrub(item, depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_scrub(item, depth + 1) for item in value]
    return value


def before_send(event: Event, hint: Hint) -> Event:
    """Remove personal data from an event before it is sent."""
    request = event.get("request")
    if request is not None:
        request.pop("data", None)
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                name: v for name, v in headers.items() if name.lower() in SAFE_HEADERS
            }
    user = event.get("user")
    if user is not None:
        # Only an opaque id (if we ever set one); never email, IP address or username.
        if "id" in user:
            event["user"] = {"id": user["id"]}
        else:
            del event["user"]
    scrubbed: Event = _scrub(event, 0)
    return scrubbed


def init_sentry() -> bool:
    """Initialise Sentry if SENTRY_DSN is set. Returns whether it was initialised."""
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    sentry_sdk.init(
        dsn=dsn,
        # development / preview / production; the SDK would default to "production".
        environment=os.environ.get("SENTRY_ENVIRONMENT") or "development",
        # Git SHA of the deployed image, set at deploy time (#33).
        release=os.environ.get("SENTRY_RELEASE") or None,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        # Errors only: performance tracing stays off (no traces_sample_rate).
        before_send=before_send,
        # The FastAPI/Starlette integrations are enabled automatically.
    )
    return True
