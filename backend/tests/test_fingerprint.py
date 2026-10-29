"""发现项指纹：稳定性、区分度与告警去重键。"""
from app.utils.fingerprint import build_dedup_key, build_fingerprint


def test_fingerprint_stable_and_40_hex():
    a = build_fingerprint(1, "repo.free_space", "repo:abc")
    b = build_fingerprint(1, "repo.free_space", "repo:abc")
    assert a == b
    assert len(a) == 40
    assert all(c in "0123456789abcdef" for c in a)


def test_fingerprint_changes_with_target_rule_or_subject():
    base = build_fingerprint(1, "repo.free_space", "repo:abc")
    assert base != build_fingerprint(2, "repo.free_space", "repo:abc")
    assert base != build_fingerprint(1, "repo.offline", "repo:abc")
    assert base != build_fingerprint(1, "repo.free_space", "repo:def")


def test_dedup_key_depends_on_alert_rule():
    fp = build_fingerprint(1, "repo.free_space", "repo:abc")
    k1 = build_dedup_key(1, fp)
    k2 = build_dedup_key(2, fp)
    assert k1 == build_dedup_key(1, fp)
    assert k1 != k2
    assert len(k1) == 40
