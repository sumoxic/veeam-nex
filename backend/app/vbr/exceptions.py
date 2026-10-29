"""VBR REST API 异常体系。

LicenseRestricted 保留：虽然当前部署是 EnterprisePlus（全端点可用），
但 Community/Free 许可会在服务端按许可证拦截大部分端点，
换到别的部署时必须显式暴露能力缺口而不是静默失败。
"""


class VbrError(Exception):
    """VBR API 调用失败的基类。"""


class LicenseRestricted(VbrError):
    """服务端因许可证不足拒绝了该调用。"""


class NotFound(VbrError):
    """端点或对象不存在。"""


class AuthError(VbrError):
    """认证失败（401）。"""


class PagingOverflow(VbrError):
    """翻页超过硬上限，采集结果可能不完整。"""


def is_license_message(message: str) -> bool:
    """判断错误消息是否是许可证限制。"""
    return "license restriction" in (message or "").lower()
