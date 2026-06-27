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
    assert "样例值里的真实标签" in prompt


def test_text2sql_prompt_requires_calculated_columns_for_comparison_tables() -> None:
    prompt = AiAdapter()._build_text2sql_prompt(
        "算一下佛山和广州的街道数量，看他们差多少，并生成一张计算表格",
        "table t(city_name, street_count)",
    )

    assert "差值" in prompt
    assert "计算列" in prompt
    assert "不要只在解释里" in prompt


def test_text2sql_prompt_uses_general_schema_linking_instead_of_domain_rules() -> None:
    prompt = AiAdapter()._build_text2sql_prompt(
        "查询客户A的销售额",
        'CREATE TABLE "orders" ("客户名称" VARCHAR -- samples: 客户A, 客户B, "金额" DOUBLE);',
    )

    assert "Schema linking" in prompt
    assert "样例值" in prompt
    assert "行政区划" not in prompt
    assert "市、县、区、镇、乡、街道、村" not in prompt


def test_text2sql_prompt_explains_row_examples_as_whole_rows() -> None:
    prompt = AiAdapter()._build_text2sql_prompt(
        "查询某个指标在1978年的值",
        '-- row_examples: [{"指标":"甲指标","1978":1.0}]\nCREATE TABLE "table_1" ("指标" VARCHAR, "1978" DOUBLE);',
    )

    assert "row_examples" in prompt
    assert "整行样例" in prompt
    assert "对应关系" in prompt


def test_agent_route_prompt_describes_model_driven_routes() -> None:
    prompt = AiAdapter()._build_agent_route_prompt("生成一张统计表")

    assert "query_only" in prompt
    assert "report_generation" in prompt
    assert "operation_planning" in prompt
    assert "只返回 JSON" in prompt


def test_classify_agent_route_parses_valid_model_route(monkeypatch) -> None:
    adapter = AiAdapter()
    monkeypatch.setattr(adapter, "_post_chat", lambda prompt, temperature: '{"route":"report_generation"}')

    assert adapter.classify_agent_route("生成一张统计表") == "report_generation"


def test_classify_agent_route_rejects_unknown_model_route(monkeypatch) -> None:
    adapter = AiAdapter()
    monkeypatch.setattr(adapter, "_post_chat", lambda prompt, temperature: '{"route":"delete_files"}')

    with pytest.raises(AiResponseError, match="路由不合法"):
        adapter.classify_agent_route("删除所有文件")


def test_suggest_collection_metadata_parses_tags_and_metadata(monkeypatch) -> None:
    adapter = AiAdapter()
    monkeypatch.setattr(
        adapter,
        "_post_chat",
        lambda prompt, temperature: '{"tags":["财务","财务"," "],"metadata":{"owner":"数据组","empty":"","nested":{"x":1}}}',
    )

    suggestion = adapter.suggest_collection_metadata("资料集")

    assert suggestion == {"tags": ["财务"], "metadata": {"owner": "数据组"}}


def test_http_429_error_message_mentions_rate_limit() -> None:
    response = httpx.Response(429, request=httpx.Request("POST", "https://example.test"))
    error = httpx.HTTPStatusError("rate limited", request=response.request, response=response)

    with pytest.raises(AiResponseError, match="限流"):
        AiAdapter()._raise_status_error(error)
