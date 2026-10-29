"""VBR REST API 客户端。

认证走 OAuth2 password grant，访问令牌有效期 15 分钟，过期自动重新登录。
VBR 默认使用自签名证书，因此默认不校验 TLS。
"""
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from app.vbr.exceptions import (
    AuthError,
    LicenseRestricted,
    NotFound,
    VbrError,
    is_license_message,
)

DEFAULT_PORT = 9419
DEFAULT_API_VERSION = "1.3-rev2"
#: VBR 大版本 → REST API 版本
API_VERSION_BY_MAJOR = {"12": "1.2-rev1", "13": "1.3-rev2"}
#: 自动探测时按新到旧尝试
AUTO_API_VERSIONS = ("1.3-rev2", "1.2-rev1")
#: 令牌到期前多少秒就主动刷新
TOKEN_REFRESH_MARGIN = 60


class VbrClient:
    """Veeam VBR REST API 客户端。

    线程安全性：每个请求线程应使用独立实例（令牌状态保存在实例上）。
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = DEFAULT_PORT,
        verify_tls: bool = False,
        timeout: int = 60,
        api_version: str | None = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.base_url = f"https://{host}:{port}"
        #: None 表示自动探测；str 表示用户指定或此前缓存的结果
        self.api_version = api_version or DEFAULT_API_VERSION
        self._auto_version = api_version is None
        self._version_resolved = api_version is not None
        self._detecting = False
        self._token: str | None = None
        #: 令牌失效的 monotonic 时刻；用 monotonic 而非 wall clock，避免系统时间调整导致误判
        self._token_deadline: float = 0.0
        self._ctx = ssl.create_default_context()
        if not verify_tls:
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE

    # ------------------------------------------------------------------ 认证

    def login(self) -> dict:
        """用账号口令换取访问令牌。"""
        body = urllib.parse.urlencode(
            {
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            }
        ).encode()
        req = urllib.request.Request(
            self.base_url + "/api/oauth2/token", data=body, method="POST"
        )
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        # VBR 12 的令牌端点同样校验 x-api-version，缺省会返回 411/400
        req.add_header("x-api-version", self.api_version)
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:300]
            # 版本不被支持不是凭据错误，交由 ensure_version 换版本重试
            if "unsupported restapi version" in detail.lower():
                raise VbrError(f"REST API 版本 {self.api_version} 不受支持: {detail}") from exc
            raise AuthError(f"登录失败 ({exc.code}): {detail}") from exc
        except OSError as exc:
            raise VbrError(f"无法连接 {self.base_url}: {exc}") from exc

        self._token = payload["access_token"]
        # 实测返回体为 {"expires_in": 900, ".expires": "<绝对时刻>"}；
        # expires_in 是「时长」，必须换算成截止时刻，否则过期后永远不刷新。
        ttl = payload.get("expires_in") or payload.get(".expires_in") or 900
        self._token_deadline = time.monotonic() + float(ttl)
        return payload

    def ensure_version(self) -> str:
        """确定可用的 REST API 版本。

        用户指定版本时直接采用；auto 模式按 1.3 → 1.2 顺序探测，
        结果缓存在实例上，同一次巡检不会重复探测。
        """
        if self._version_resolved:
            return self.api_version

        last_error: Exception | None = None
        self._detecting = True
        try:
            for version in AUTO_API_VERSIONS:
                self.api_version = version
                self._token = None
                self._token_deadline = 0.0
                try:
                    self.login()
                    info = self._request("GET", "/api/v1/serverInfo", _retry_auth=False)
                except AuthError:
                    # 凭据错误与版本无关，直接上抛
                    raise
                except VbrError as exc:
                    last_error = exc
                    continue
                if isinstance(info, dict) and info.get("buildVersion"):
                    self._version_resolved = True
                    return version
        finally:
            self._detecting = False
        raise last_error or VbrError("无法确定 VBR 的 REST API 版本")

    def _ensure_token(self) -> str:
        """确保有可用令牌，必要时重新登录。"""
        if self._auto_version and not self._version_resolved and not self._detecting:
            self.ensure_version()
        if self._token is None or self._token_deadline - time.monotonic() <= TOKEN_REFRESH_MARGIN:
            self.login()
        return self._token  # type: ignore[return-value]

    # ------------------------------------------------------------------ 请求

    def _request(self, method: str, path: str, query: dict | None = None,
                 body: dict | None = None, _retry_auth: bool = True) -> object:
        """发起一次 API 调用。

        遇到 401 会作废令牌、重新登录并重放一次；令牌在服务端被提前失效时
        （例如管理员改密）靠这一层自愈。
        """
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "Authorization": "Bearer " + self._ensure_token(),
            "x-api-version": self.api_version,
        }
        if data:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=self.timeout) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw.strip() else None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                err = json.loads(raw)
                message = err.get("message") or err.get("title") or raw[:200]
            except (ValueError, AttributeError):
                message = raw[:200]
            if exc.code == 401:
                if _retry_auth:
                    self._token = None
                    self._token_deadline = 0.0
                    return self._request(method, path, query=query, body=body, _retry_auth=False)
                raise AuthError(f"未授权: {message}") from exc
            if is_license_message(message):
                raise LicenseRestricted(message) from exc
            if exc.code == 404:
                raise NotFound(f"{path}: {message}") from exc
            raise VbrError(f"{method} {path} 失败 ({exc.code}): {message}") from exc
        except OSError as exc:
            raise VbrError(f"{method} {path} 请求失败: {exc}") from exc

    def get(self, path: str, **query) -> object:
        """GET 请求。"""
        return self._request("GET", path, query=query or None)

    def post(self, path: str, body: dict | None = None) -> object:
        """POST 请求。"""
        return self._request("POST", path, body=body)

    # ------------------------------------------------------------- 能力探测

    def available(self) -> dict:
        """探测各巡检端点在当前部署上是否可用。

        结果用于「能力缺口」展示：Community 许可下被封锁的端点必须显式呈现。
        """
        from app.vbr.endpoints import inspection_endpoints

        self.ensure_version()
        results: dict[str, str] = {}
        for path in inspection_endpoints(self.api_version):
            try:
                self.get(path)
                results[path] = "ok"
            except LicenseRestricted:
                results[path] = "license-restricted"
            except NotFound:
                results[path] = "not-found"
            except AuthError:
                results[path] = "unauthorized"
            except VbrError as exc:
                results[path] = f"error: {exc}"
        return results
