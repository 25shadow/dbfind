from app.services.table_metadata_extractor import TableMetadataExtractor


def test_table_metadata_extractor_gets_title_subtitle_and_unit_from_raw_blocks():
    metadata = TableMetadataExtractor().extract(
        [
            {"region": "A1:A1", "text": "2-2  地区生产总值", "cells": ["A1"]},
            {"region": "A2:A2", "text": "Gross Domestic Product", "cells": ["A2"]},
            {"region": "A4:L4", "text": "单位：亿元 (100 million yuan)", "cells": ["A4", "L4"]},
            {"region": "B5:B5", "text": "地区生", "cells": ["B5"]},
        ]
    )

    assert metadata == {
        "title": "2-2 地区生产总值",
        "subtitle": "Gross Domestic Product",
        "unit": "单位：亿元 (100 million yuan)",
    }


def test_table_metadata_extractor_treats_base_statement_as_unit():
    metadata = TableMetadataExtractor().extract(
        [
            {"region": "A1:A1", "text": "2-3  地区生产总值指数", "cells": ["A1"]},
            {"region": "A2:A2", "text": "Indices of Gross Domestic Product", "cells": ["A2"]},
            {"region": "A4:L4", "text": "上年=100 (preceding year=100)", "cells": ["A4", "L4"]},
        ]
    )

    assert metadata["title"] == "2-3 地区生产总值指数"
    assert metadata["subtitle"] == "Indices of Gross Domestic Product"
    assert metadata["unit"] == "上年=100 (preceding year=100)"
