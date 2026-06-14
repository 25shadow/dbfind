from app.services.collection_name_parser import CollectionNameParser


def test_parses_province_rural_yearbook_name() -> None:
    parsed = CollectionNameParser().parse("广东省2022年农村统计年鉴")

    assert parsed.source_region == "广东省"
    assert parsed.source_year == 2022
    assert parsed.source_type == "农村统计年鉴"
    assert parsed.source_scope == "province"


def test_parses_city_yearbook_name() -> None:
    parsed = CollectionNameParser().parse("韶关市2022年统计年鉴")

    assert parsed.source_region == "韶关市"
    assert parsed.source_year == 2022
    assert parsed.source_type == "统计年鉴"
    assert parsed.source_scope == "city"


def test_keeps_unknown_parts_empty_when_name_is_ambiguous() -> None:
    parsed = CollectionNameParser().parse("农业数据汇总")

    assert parsed.source_region is None
    assert parsed.source_year is None
    assert parsed.source_type is None
    assert parsed.source_scope is None
