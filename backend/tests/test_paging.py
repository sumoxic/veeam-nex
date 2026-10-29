"""翻页遍历：多页、短页、空页与翻页上限。"""
import pytest

from app.vbr.exceptions import PagingOverflow
from app.vbr.paging import iter_all


def _payload(items):
    return {"data": items, "pagination": {"total": len(items)}}


def test_single_short_page():
    calls = []

    def fetch(offset, limit):
        calls.append((offset, limit))
        return _payload([{"id": 1}])

    assert list(iter_all(fetch, page_size=200)) == [{"id": 1}]
    assert calls == [(0, 200)]


def test_multi_page_until_short_page():
    pages = {
        0: [{"id": i} for i in range(200)],
        200: [{"id": 200 + i} for i in range(200)],
        400: [{"id": 400}, {"id": 401}],
    }
    calls = []

    def fetch(offset, limit):
        calls.append(offset)
        return _payload(pages[offset])

    items = list(iter_all(fetch, page_size=200))
    assert len(items) == 402
    assert calls == [0, 200, 400]
    assert items[-1] == {"id": 401}


def test_empty_payload_stops():
    def fetch(offset, limit):
        return _payload([])

    assert list(iter_all(fetch, page_size=200)) == []


def test_non_dict_payload_stops():
    def fetch(offset, limit):
        return None

    assert list(iter_all(fetch, page_size=200)) == []


def test_overflow_raises():
    def fetch(offset, limit):
        return _payload([{"id": offset + i} for i in range(limit)])

    with pytest.raises(PagingOverflow):
        list(iter_all(fetch, page_size=10, max_pages=3))
