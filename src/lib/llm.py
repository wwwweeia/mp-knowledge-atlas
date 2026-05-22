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


SUMMARIZE_PROMPT = """\
请对以下技术文章生成结构化摘要。输出严格的 JSON 格式：
{{"summary": "200字以内的中文摘要", "keywords": ["关键词1", "关键词2", "关键词3"]}}

要求：
- summary 准确概括文章的核心内容和技术要点
- keywords 是 3-5 个最能代表文章主题的词
- 如果文章是活动/招聘/公告类非技术内容，keywords 中包含"非技术"

文章标题：{title}
文章正文：
{text}"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((APIConnectionError, RateLimitError)),
    reraise=True,
)
def summarize_article(
    title: str, text: str, *, client: OpenAI | None = None
) -> dict:
    cli = client or get_client()
    prompt = SUMMARIZE_PROMPT.format(title=title, text=text[:8000])
    resp = cli.chat.completions.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    content = resp.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return JSON: {content!r}") from e
