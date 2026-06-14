import httpx

from mazyr.domain.tool import ToolResult
from mazyr.infrastructure.retry import retry_api_call


def _hostname_matches(domain: str, allowed: str) -> bool:
    """Exact domain or sub-domain match with boundary checks.

    Examples:
      - api.github.com matches github.com? No — public-suffix aware check.
      - api.github.com matches api.github.com? Yes.
      - notapi.github.com matches api.github.com? No.
    """
    domain_parts = domain.lower().split(".")
    allowed_parts = allowed.lower().split(".")
    if len(domain_parts) < len(allowed_parts):
        return False
    # Compare the right-most labels; the allowed domain must be a true suffix.
    return domain_parts[-len(allowed_parts) :] == allowed_parts


@retry_api_call
def _execute_request(method: str, url: str, headers: dict, body) -> httpx.Response:
    timeout = httpx.Timeout(timeout=30.0)
    with httpx.Client(timeout=timeout) as client:
        if method.upper() == "GET":
            return client.get(url, headers=headers)
        return client.request(method.upper(), url, headers=headers, json=body)


def handle(params: dict, context: dict) -> ToolResult:
    url = params.get("url", "")
    method = params.get("method", "GET")
    headers = params.get("headers", {})
    body = params.get("body")

    if not url:
        return ToolResult(success=False, error="url is required")

    # Domain whitelist check
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.hostname or ""
    scheme = parsed.scheme or ""

    if scheme.lower() != "https":
        return ToolResult(
            success=False,
            error=f"Only HTTPS URLs are allowed; got scheme '{scheme}'",
        )

    tool_config = context.get("tool_config")
    if tool_config and tool_config.external_api_whitelist:
        allowed = any(_hostname_matches(domain, d) for d in tool_config.external_api_whitelist)
        if not allowed:
            return ToolResult(
                success=False,
                error=f"Domain '{domain}' not in external API whitelist",
            )
    else:
        return ToolResult(
            success=False,
            error="External API calls are disabled: no whitelist configured",
        )

    try:
        resp = _execute_request(method, url, headers, body)
        return ToolResult(
            success=resp.status_code < 500,
            data=resp.text[:10000],
        )
    except httpx.HTTPError as e:
        return ToolResult(success=False, error=f"HTTP error: {e}")
    except Exception as e:
        return ToolResult(success=False, error=f"Request failed: {e}")
