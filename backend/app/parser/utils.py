"""文档解析通用工具函数."""


def extract_year(filename: str) -> int | None:
    """从文件名提取 4 位年份."""
    name = filename.rsplit(".", 1)[0] if "." in filename else filename
    for token in name.replace("_", "-").split("-"):
        if token.isdigit() and len(token) == 4:
            return int(token)
    return None


def extract_period(filename: str) -> str | None:
    """从文件名提取季度/月份标识."""
    name = filename.rsplit(".", 1)[0] if "." in filename else filename
    lowered = name.lower()
    for marker in ("q1", "q2", "q3", "q4", "h1", "h2"):
        if marker in lowered:
            return marker.upper()
    return None
