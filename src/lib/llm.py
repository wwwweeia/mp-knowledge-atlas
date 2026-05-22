"""Claude Haiku client for cluster naming."""

import json
import os

from anthropic import Anthropic, APIConnectionError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

MODEL = "claude-haiku-4-5-20251001"

PROMPT = """\
你是技术内容编辑。下面是一组属于同一聚类的文章标题，请用中文给这个聚类起一个 \
6-12 字的领域名称，并写一句不超过 40 字的领域描述。

只输出 JSON：{{"name": "<领域名>", "description": "<一句话描述>"}}

标题列表：
{titles}"""


def get_client() -> Anthropic:
    """Create Anthropic client from environment variable."""
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((APIConnectionError, RateLimitError)),
    reraise=True,
)
def name_cluster(titles: list[str], *, client: Anthropic | None = None) -> dict:
    """Ask Claude Haiku to name a cluster given a list of article titles.

    Args:
        titles: Article titles belonging to the cluster (max 20 sent to LLM).
        client: Optional Anthropic client for testing.

    Returns:
        Dict with "name" and "description" keys.

    Raises:
        ValueError: If LLM response is not valid JSON.
        APIConnectionError: If all retry attempts fail on connection errors.
        RateLimitError: If all retry attempts fail on rate limits.
    """
    cli = client or get_client()
    prompt = PROMPT.format(titles="\n".join(f"- {t}" for t in titles[:20]))
    resp = cli.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return JSON: {text!r}") from e
