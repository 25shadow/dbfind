import pytest
import httpx

from app.adapters.ai_adapter import AiAdapter, AiResponseError


def test_extract_content_rejects_empty_choices() -> None:
    with pytest.raises(AiResponseError, match="AI 服务返回格式异常"):
        AiAdapter()._extract_content({"choices": None})


def test_extract_content_rejects_empty_choice_list() -> None:
    with pytest.raises(AiResponseError, match="AI 服务返回格式异常"):
        AiAdapter()._extract_content({"choices": []})


def test_text2sql_prompt_warns_against_using_generic_column_numbers_as_years() -> None:
    prompt = AiAdapter()._build_text2sql_prompt(
        "查询各年的指标",
        'CREATE TABLE "table_1" ("2" DOUBLE -- samples: nan, 2000.0, 1419.91);',
    )

    assert "不要把泛化列名" in prompt
    assert "样例值里的年份" in prompt


def test_text2sql_prompt_requires_calculated_columns_for_comparison_tables() -> None:
    prompt = AiAdapter()._build_text2sql_prompt(
        "算一下佛山和广州的街道数量，看他们差多少，并生成一张计算表格",
        "table t(city_name, street_count)",
    )

    assert "差值" in prompt
    assert "计算列" in prompt
    assert "不要只在解释里" in prompt


def test_text2sql_prompt_explains_row_examples_as_whole_rows() -> None:
    prompt = AiAdapter()._build_text2sql_prompt(
        "查询某个指标在1978年的值",
        '-- row_examples: [{"指标":"甲指标","1978":1.0}]\nCREATE TABLE "table_1" ("指标" VARCHAR, "1978" DOUBLE);',
    )

    assert "row_examples" in prompt
    assert "整行样例" in prompt
    assert "对应关系" in prompt


def test_http_429_error_message_mentions_rate_limit() -> None:
    response = httpx.Response(429, request=httpx.Request("POST", "https://example.test"))
    error = httpx.HTTPStatusError("rate limited", request=response.request, response=response)

    with pytest.raises(AiResponseError, match="限流"):
        AiAdapter()._raise_status_error(error)
