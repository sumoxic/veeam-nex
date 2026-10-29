"""发现项指纹。

指纹用于跨轮次稳定识别同一个问题：同一目标 + 同一规则 + 同一对象 = 同一个指纹。
"""
import hashlib


def build_fingerprint(target_id: int, rule_key: str, subject_key: str) -> str:
    """构造 40 位十六进制指纹。

    subject_key 必须是机器可读的对象标识（如 "job:<uuid>"），
    不能用会随参数变化的消息文本，否则指纹会漂移。
    """
    raw = f"{target_id}|{rule_key}|{subject_key}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def build_dedup_key(alert_rule_id: int, fingerprint: str) -> str:
    """告警去重键：同一规则对同一问题的重复告警共享。"""
    raw = f"{alert_rule_id}|{fingerprint}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
