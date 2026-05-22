import json
from unittest.mock import MagicMock

import pytest

from src.lib.llm import name_cluster


class TestNameCluster:
    def test_returns_parsed_json(self):
        fake = MagicMock()
        fake.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=json.dumps(
                            {"name": "AI Coding", "description": "AI 辅助编程相关讨论"},
                            ensure_ascii=False,
                        )
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
        fake = MagicMock()
        fake.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json"))]
        )
        with pytest.raises(ValueError, match="LLM did not return JSON"):
            name_cluster(["x"], client=fake)

    def test_truncates_titles_to_twenty(self):
        fake = MagicMock()
        fake.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=json.dumps(
                            {"name": "T", "description": "D"}, ensure_ascii=False
                        )
                    )
                )
            ]
        )
        titles = [f"Article {i}" for i in range(25)]
        name_cluster(titles, client=fake)

        call_args = fake.chat.completions.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        for i in range(20, 25):
            assert f"Article {i}" not in prompt
        assert "Article 0" in prompt
        assert "Article 19" in prompt
