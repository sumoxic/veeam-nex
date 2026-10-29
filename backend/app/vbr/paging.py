"""VBR 列表端点翻页。

VBR 的列表端点单页上限 200 条，直接取 limit=200 会在对象数量多时静默丢数据。
"""
from typing import Any, Callable, Iterator

from app.vbr.exceptions import PagingOverflow, VbrError

#: 单页条数，与 VBR 上限一致
PAGE_SIZE = 200
#: 翻页硬上限，防止异常情况下无限翻页
MAX_PAGES = 50


def iter_all(
    fetch: Callable[[int, int], Any],
    *,
    page_size: int = PAGE_SIZE,
    max_pages: int = MAX_PAGES,
) -> Iterator[dict]:
    """逐页遍历列表端点的全部数据。

    fetch(offset, limit) 需返回 VBR 的标准响应体 {"data": [...], "pagination": {...}}。
    翻到返回条数小于 page_size 的短页为止。
    """
    offset = 0
    for _ in range(max_pages):
        payload = fetch(offset, page_size)
        if not isinstance(payload, dict):
            return
        items = payload.get("data") or []
        if not items:
            return
        yield from items
        if len(items) < page_size:
            return
        offset += page_size
    raise PagingOverflow(
        f"翻页超过 {max_pages} 页上限，数据可能不完整，请缩小采集范围或调整 page_size"
    )


def iter_items(
    client,
    path: str,
    *,
    page_size: int = PAGE_SIZE,
    max_pages: int = MAX_PAGES,
) -> list[dict]:
    """遍历指定列表端点的全部条目。"""

    def fetch(offset: int, limit: int) -> Any:
        # VBR 的分页参数是 skip（不是 offset）
        return client.get(path, limit=limit, skip=offset)

    try:
        return list(iter_all(fetch, page_size=page_size, max_pages=max_pages))
    except PagingOverflow:
        raise
    except VbrError:
        raise
