from dataclasses import dataclass
import re

import pandas as pd


@dataclass(frozen=True)
class MergedCellRange:
    start_row: int
    end_row: int
    start_col: int
    end_col: int


@dataclass(frozen=True)
class ExcelSheetSignals:
    merged_ranges: list[MergedCellRange] | None = None
    styled_rows: set[int] | None = None


@dataclass(frozen=True)
class ExcelStructure:
    header_start: int | None
    header_end: int | None
    data_start: int
    title_rows: list[int]
    confidence: str
    reasons: list[str]


@dataclass(frozen=True)
class _RowProfile:
    index: int
    non_empty_count: int
    text_count: int
    header_like_count: int
    year_count: int
    numeric_non_year_count: int


class ExcelStructureDetector:
    """Detect title, header, and data regions in small Excel-like grids."""

    def detect(
        self,
        dataframe: pd.DataFrame,
        signals: ExcelSheetSignals | None = None,
        row_offset: int = 0,
    ) -> ExcelStructure:
        if len(dataframe.index) < 1 or len(dataframe.columns) < 2:
            return ExcelStructure(None, None, 0, [], "none", ["too_small"])

        signals = signals or ExcelSheetSignals()
        profiles = [
            self._profile_row(
                index,
                list(dataframe.iloc[index]),
                signals=signals,
                row_offset=row_offset,
            )
            for index in range(min(8, len(dataframe.index)))
        ]
        candidates = [
            (self._score_header_candidate(profile, profiles, signals, row_offset), profile)
            for profile in profiles
        ]
        candidates = [(score, profile) for score, profile in candidates if score > 0]
        if not candidates:
            return ExcelStructure(None, None, 0, [], "none", ["no_header_candidate"])

        score, best = max(candidates, key=lambda item: item[0])
        header_end = self._find_header_end(dataframe, best.index, signals, row_offset)
        title_rows = self._title_rows_before(profiles, best.index, signals, row_offset)
        confidence = "high" if score >= 16 else "medium"
        reasons = self._reasons(best, header_end, title_rows, signals, row_offset)
        return ExcelStructure(
            header_start=best.index,
            header_end=header_end,
            data_start=header_end + 1,
            title_rows=title_rows,
            confidence=confidence,
            reasons=reasons,
        )

    def detect_regions(
        self,
        dataframe: pd.DataFrame,
        signals: ExcelSheetSignals | None = None,
    ) -> list[ExcelStructure]:
        regions: list[ExcelStructure] = []
        start = 0
        while start < len(dataframe.index):
            while start < len(dataframe.index) and self._is_blank_row(list(dataframe.iloc[start])):
                start += 1
            if start >= len(dataframe.index):
                break

            end = start
            while end < len(dataframe.index) and not self._is_blank_row(list(dataframe.iloc[end])):
                end += 1

            segment = dataframe.iloc[start:end].reset_index(drop=True)
            structure = self.detect(segment, signals=signals, row_offset=start)
            if structure.header_start is not None and structure.header_end is not None:
                regions.append(
                    ExcelStructure(
                        header_start=structure.header_start + start,
                        header_end=structure.header_end + start,
                        data_start=structure.data_start + start,
                        title_rows=[row + start for row in structure.title_rows],
                        confidence=structure.confidence,
                        reasons=structure.reasons,
                    )
                )
            start = end + 1
        return regions

    def _score_header_candidate(
        self,
        profile: _RowProfile,
        profiles: list[_RowProfile],
        signals: ExcelSheetSignals,
        row_offset: int,
    ) -> int:
        if profile.non_empty_count < 2:
            return 0
        if profile.header_like_count < max(2, profile.non_empty_count // 2):
            return 0
        is_styled = self._is_styled_row(profile.index + row_offset, signals)
        if profile.text_count < 2 and not is_styled:
            return 0
        if profile.numeric_non_year_count > profile.header_like_count:
            return 0

        score = (
            profile.header_like_count
            + profile.text_count * 2
            + profile.year_count * 2
        )
        next_profile = self._profile_after(profiles, profile.index)
        if next_profile and self._looks_like_data_after_header(next_profile):
            score += 5
        previous_profile = self._profile_before(profiles, profile.index)
        if previous_profile and self._looks_like_title(previous_profile):
            score += 2
        if is_styled:
            score += 5
        return score

    def _find_header_end(
        self,
        dataframe: pd.DataFrame,
        header_start: int,
        signals: ExcelSheetSignals,
        row_offset: int,
    ) -> int:
        header_end = header_start
        for index in range(header_start + 1, min(header_start + 4, len(dataframe.index))):
            profile = self._profile_row(
                index,
                list(dataframe.iloc[index]),
                signals=signals,
                row_offset=row_offset,
            )
            if profile.non_empty_count == 0:
                break
            if profile.header_like_count != profile.non_empty_count:
                break
            header_end = index
        return header_end

    def _title_rows_before(
        self,
        profiles: list[_RowProfile],
        header_start: int,
        signals: ExcelSheetSignals,
        row_offset: int,
    ) -> list[int]:
        return [
            profile.index
            for profile in profiles
            if profile.index < header_start
            and (
                self._looks_like_title(profile)
                or self._has_merged_range_on_row(profile.index + row_offset, signals)
            )
        ]

    def _reasons(
        self,
        profile: _RowProfile,
        header_end: int,
        title_rows: list[int],
        signals: ExcelSheetSignals,
        row_offset: int,
    ) -> list[str]:
        reasons = []
        if profile.year_count:
            reasons.append("year_header_cells")
        if header_end > profile.index:
            reasons.append("multi_row_header")
        if self._is_styled_row(profile.index + row_offset, signals):
            reasons.append("styled_header_row")
        if any(self._has_merged_range_on_row(row + row_offset, signals) for row in title_rows):
            reasons.append("merged_title_row")
        return reasons or ["header_like_row"]

    def _profile_before(
        self,
        profiles: list[_RowProfile],
        index: int,
    ) -> _RowProfile | None:
        for profile in reversed(profiles):
            if profile.index < index:
                return profile
        return None

    def _profile_after(
        self,
        profiles: list[_RowProfile],
        index: int,
    ) -> _RowProfile | None:
        for profile in profiles:
            if profile.index > index:
                return profile
        return None

    def _looks_like_data_after_header(self, profile: _RowProfile) -> bool:
        return profile.non_empty_count >= 2 and profile.numeric_non_year_count > 0

    def _looks_like_title(self, profile: _RowProfile) -> bool:
        return (
            profile.non_empty_count <= 2
            and profile.text_count >= 1
            and profile.numeric_non_year_count == 0
        )

    def _profile_row(
        self,
        index: int,
        values: list,
        signals: ExcelSheetSignals | None = None,
        row_offset: int = 0,
    ) -> _RowProfile:
        non_empty_count = 0
        text_count = 0
        header_like_count = 0
        year_count = 0
        numeric_non_year_count = 0

        for value in values:
            if not self._has_value(value):
                continue
            non_empty_count += 1
            text = self._cell_to_text(value)
            is_year = self._looks_year(text)
            is_text = self._is_text(value)
            if is_text:
                text_count += 1
            if is_year:
                year_count += 1
            elif self._looks_numeric(text):
                numeric_non_year_count += 1
            if is_text or is_year:
                header_like_count += 1

        return _RowProfile(
            index=index,
            non_empty_count=non_empty_count,
            text_count=text_count,
            header_like_count=header_like_count,
            year_count=year_count,
            numeric_non_year_count=numeric_non_year_count,
        )

    def _is_blank_row(self, values: list) -> bool:
        return not any(self._has_value(value) for value in values)

    def _is_styled_row(self, row_index: int, signals: ExcelSheetSignals) -> bool:
        return row_index in (signals.styled_rows or set())

    def _has_merged_range_on_row(self, row_index: int, signals: ExcelSheetSignals) -> bool:
        return any(
            merged.start_row <= row_index <= merged.end_row and merged.end_col > merged.start_col
            for merged in (signals.merged_ranges or [])
        )

    def _is_text(self, value) -> bool:
        if not self._has_value(value):
            return False
        return not self._looks_numeric(self._cell_to_text(value))

    def _has_value(self, value) -> bool:
        if pd.isna(value):
            return False
        return bool(str(value).strip())

    def _cell_to_text(self, value) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        text = str(value).replace("\u3000", " ")
        text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _looks_numeric(self, value: str) -> bool:
        return bool(re.fullmatch(r"[-+]?\d+(\.\d+)?%?", value.strip()))

    def _looks_year(self, value: str) -> bool:
        return bool(re.fullmatch(r"(?:19|20)\d{2}(?:\.0)?", value.strip()))
