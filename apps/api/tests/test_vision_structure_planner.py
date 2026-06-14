from app.services.excel_cell_grid import RawCell, RawCellGrid
from app.services.sheet_renderer import SheetRendering
from app.services.vision_structure_planner import VisionStructurePlanner


class Settings:
    ai_base_url = "https://example.test"
    ai_chat_path = "/v1/chat/completions"
    model = "vision-model"
    api_key = "test-key"
    vision_ai_base_url = "https://vision.example.test"
    vision_ai_chat_path = "/v1/chat/completions"
    vision_model = "gpt-4o"
    vision_api_key = "vision-key"


def test_vision_structure_planner_sends_screenshot_and_returns_coordinate_plan(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"tableRegion":"A2:B3","titleRows":[1],"unitCells":[],"headerRows":[2],"dataStartRow":3,"dataEndRow":3,"rowHeaderColumns":["A"],"valueColumns":["B"],"categoryRows":[],"orientation":"wide_table","confidence":0.88,"source":"vlm"}'
                        }
                    }
                ]
            }

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, json, headers):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return Response()

    monkeypatch.setattr("app.services.vision_structure_planner.SettingsService.get", lambda self: Settings())
    monkeypatch.setattr("app.services.vision_structure_planner.httpx.Client", Client)

    rendering = SheetRendering(
        sheet_name="Sheet1",
        region="A1:B3",
        html="<table></table>",
        png_base64="iVBOR-test",
        grid_summary=[],
    )
    grid = RawCellGrid(
        sheet_name="Sheet1",
        max_row=3,
        max_col=2,
        cells=[
            RawCell(1, 1, "A1", "Title"),
            RawCell(2, 1, "A2", "Name"),
            RawCell(2, 2, "B2", 2024),
            RawCell(3, 1, "A3", "Alpha"),
            RawCell(3, 2, "B3", 1.2),
        ],
        merged_ranges=[],
    )

    plan = VisionStructurePlanner().plan(grid, rendering)

    assert plan is not None
    assert plan.source == "vlm"
    assert plan.header_rows == [2]
    assert captured["url"] == "https://vision.example.test/v1/chat/completions"
    assert captured["json"]["model"] == "gpt-4o"
    assert captured["headers"]["Authorization"] == "Bearer vision-key"
    content = captured["json"]["messages"][1]["content"]
    assert content[0]["type"] == "text"
    assert "wide_table | wide_year_table" not in content[0]["text"]
    assert "wide_table, wide_year_table, long_table, unknown" in content[0]["text"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,iVBOR-test")


def test_vision_structure_planner_normalizes_union_orientation_from_model(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"tableRegion":"A1:C5","titleRows":[1,2],"unitCells":[],"headerRows":[4],"dataStartRow":5,"dataEndRow":5,"rowHeaderColumns":["A"],"valueColumns":["B","C"],"categoryRows":[],"orientation":"wide_table | wide_year_table","confidence":0.88,"source":"vlm"}'
                        }
                    }
                ]
            }

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, json, headers):
            return Response()

    monkeypatch.setattr("app.services.vision_structure_planner.SettingsService.get", lambda self: Settings())
    monkeypatch.setattr("app.services.vision_structure_planner.httpx.Client", Client)

    rendering = SheetRendering("Sheet1", "A1:C5", "<table></table>", "iVBOR-test", [])
    grid = RawCellGrid("Sheet1", 5, 3, [RawCell(1, 1, "A1", "Title")], [])

    plan = VisionStructurePlanner().plan(grid, rendering)

    assert plan.orientation == "wide_year_table"
    assert plan.title_rows == [1, 2]


def test_vision_structure_planner_returns_none_without_api_key(monkeypatch):
    class EmptySettings(Settings):
        vision_api_key = ""

    monkeypatch.setattr("app.services.vision_structure_planner.SettingsService.get", lambda self: EmptySettings())

    rendering = SheetRendering("Sheet1", "A1:A1", "", "iVBOR-test", [])
    grid = RawCellGrid("Sheet1", 1, 1, [RawCell(1, 1, "A1", "Only")], [])

    planner = VisionStructurePlanner()
    assert planner.availability_issue() == "vlm_api_key_missing"
    assert planner.plan(grid, rendering) is None


def test_vision_structure_planner_returns_none_without_model(monkeypatch):
    class EmptyModelSettings(Settings):
        vision_model = ""

    monkeypatch.setattr("app.services.vision_structure_planner.SettingsService.get", lambda self: EmptyModelSettings())

    rendering = SheetRendering("Sheet1", "A1:A1", "", "iVBOR-test", [])
    grid = RawCellGrid("Sheet1", 1, 1, [RawCell(1, 1, "A1", "Only")], [])

    planner = VisionStructurePlanner()
    assert planner.availability_issue() == "vlm_model_missing"
    assert planner.plan(grid, rendering) is None
