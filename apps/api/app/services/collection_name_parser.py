from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ParsedCollectionName:
    source_region: str | None
    source_year: int | None
    source_type: str | None
    source_scope: str | None


class CollectionNameParser:
    def parse(self, name: str) -> ParsedCollectionName:
        cleaned = name.strip()
        year = self._parse_year(cleaned)
        region = self._parse_region(cleaned)
        source_type = self._parse_source_type(cleaned, year)
        scope = self._parse_scope(region)

        return ParsedCollectionName(
            source_region=region,
            source_year=year,
            source_type=source_type,
            source_scope=scope,
        )

    def _parse_year(self, name: str) -> int | None:
        match = re.search(r"(19|20)\d{2}", name)
        return int(match.group(0)) if match else None

    def _parse_region(self, name: str) -> str | None:
        match = re.search(r"([\u4e00-\u9fa5]{2,12}?(?:省|市|自治区|特别行政区))", name)
        return match.group(1) if match else None

    def _parse_source_type(self, name: str, year: int | None) -> str | None:
        if "年鉴" not in name:
            return None

        text = name
        if year is not None:
            text = text.replace(f"{year}年", "", 1).replace(str(year), "", 1)

        region = self._parse_region(name)
        if region:
            text = text.replace(region, "", 1)

        text = text.strip(" -_（）()")
        return text or None

    def _parse_scope(self, region: str | None) -> str | None:
        if not region:
            return None
        if region.endswith("省") or region.endswith("自治区") or region.endswith("特别行政区"):
            return "province"
        if region.endswith("市"):
            return "city"
        return None
