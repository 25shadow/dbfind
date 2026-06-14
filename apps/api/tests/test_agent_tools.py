from app.services.agent_tools import create_excel_agent_tools


def test_excel_agent_tools_are_registered_with_expected_names():
    tools = create_excel_agent_tools()

    names = {tool.name for tool in tools}

    assert names == {
        "query_excel_data",
        "transform_dataframe",
        "write_workbook",
        "style_workbook",
    }
