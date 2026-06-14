import re


FORBIDDEN_SQL_KEYWORDS = {
    "alter",
    "attach",
    "call",
    "copy",
    "create",
    "delete",
    "drop",
    "execute",
    "insert",
    "install",
    "load",
    "pragma",
    "set",
    "update",
    "vacuum",
}


def ensure_readonly_select(sql: str) -> None:
    normalized = _strip_sql_comments(sql).strip().lower()
    if not normalized:
        raise ValueError("SQL 不能为空")

    statements = _split_sql_statements(normalized)
    if len(statements) != 1:
        raise ValueError("V1 只允许执行单条 SELECT 查询")

    statement = statements[0]
    if not (statement.startswith("select") or statement.startswith("with")):
        raise ValueError("V1 只允许执行 SELECT 查询")

    tokens = set(re.findall(r"[a-z_][a-z0-9_]*", statement))
    forbidden = tokens.intersection(FORBIDDEN_SQL_KEYWORDS)
    if forbidden:
        raise ValueError(f"SQL 包含禁止关键字：{', '.join(sorted(forbidden))}")

    if statement.startswith("with") and "select" not in tokens:
        raise ValueError("WITH 查询必须最终读取 SELECT 结果")


def _strip_sql_comments(sql: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\r\n]*", " ", without_block_comments)


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False
    escaped = False

    for char in sql:
        if escaped:
            current.append(char)
            escaped = False
            continue

        if char == "\\":
            current.append(char)
            escaped = True
            continue

        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current.append(char)
            continue

        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(char)
            continue

        if char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue

        current.append(char)

    statement = "".join(current).strip()
    if statement:
        statements.append(statement)

    return statements
