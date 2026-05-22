"""DeepSeek (OpenAI-compatible) client for cluster naming."""

import json
import os

from openai import APIConnectionError, RateLimitError, OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

MODEL = "deepseek-chat"
BASE_URL = "https://api.deepseek.com"

PROMPT = """\
你是技术内容编辑。下面是一组属于同一聚类的文章标题，请用中文给这个聚类起一个 \
6-12 字的领域名称，并写一句不超过 40 字的领域描述。

只输出 JSON：{{"name": "<领域名>", "description": "<一句话描述>"}}

标题列表：
{titles}"""


def get_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=BASE_URL,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((APIConnectionError, RateLimitError)),
    reraise=True,
)
def name_cluster(titles: list[str], *, client: OpenAI | None = None) -> dict:
    cli = client or get_client()
    prompt = PROMPT.format(titles="\n".join(f"- {t}" for t in titles[:20]))
    resp = cli.chat.completions.create(
        model=MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return JSON: {text!r}") from e
