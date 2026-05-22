import json
from unittest.mock import MagicMock

import pytest

from src.lib.llm import name_cluster


class TestNameCluster:
    def test_returns_parsed_json(self):
        """LLM returns valid JSON -> name_cluster parses it."""
        fake = MagicMock()
        fake.messages.create.return_value = MagicMock(
            content=[
                MagicMock(
                    text=json.dumps(
                        {"name": "AI Coding", "description": "AI 辅助编程相关讨论"},
                        ensure_ascii=False,
                    )
                )
            ]
        )
        result = name_cluster(["Claude Code 实战", "Cursor 用法"], client=fake)
        assert result == {
            "name": "AI Coding",
            "description": "AI 辅助编程相关讨论",
        }

    def test_raises_value_error_on_bad_json(self):
        """LLM returns non-JSON -> name_cluster raises ValueError."""
        fake = MagicMock()
        fake.messages.create.return_value = MagicMock(
            content=[MagicMock(text="not json")]
        )
        with pytest.raises(ValueError, match="LLM did not return JSON"):
            name_cluster(["x"], client=fake)

    def test_truncates_titles_to_twenty(self):
        """Only first 20 titles are sent to LLM."""
        fake = MagicMock()
        fake.messages.create.return_value = MagicMock(
            content=[
                MagicMock(
                    text=json.dumps(
                        {"name": "T", "description": "D"}, ensure_ascii=False
                    )
                )
            ]
        )
        titles = [f"Article {i}" for i in range(25)]
        name_cluster(titles, client=fake)

        call_args = fake.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        for i in range(20, 25):
            assert f"Article {i}" not in prompt
        assert "Article 0" in prompt
        assert "Article 19" in prompt
