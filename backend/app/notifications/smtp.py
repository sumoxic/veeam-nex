"""SMTP 邮件通知。"""
import smtplib
from email.message import EmailMessage

from app.notifications.base import Message, NotifyError


class SmtpNotifier:
    """通过 SMTP 服务器投递告警邮件。"""

    def __init__(self, config: dict, secret: str | None = None):
        self.host = config.get("host")
        self.port = int(config.get("port") or 25)
        self.username = config.get("username")
        self.from_addr = config.get("from_addr") or self.username
        self.to_addrs = config.get("to_addrs") or []
        self.use_ssl = bool(config.get("use_ssl"))
        self.use_starttls = bool(config.get("use_starttls"))
        self.subject_prefix = config.get("subject_prefix") or "[Veeam巡检]"
        self._secret = secret

    def send(self, message: Message) -> None:
        if not self.host:
            raise NotifyError("SMTP 渠道缺少 host 配置")
        if not self.to_addrs:
            raise NotifyError("SMTP 渠道缺少收件人 to_addrs")

        mail = EmailMessage()
        mail["Subject"] = f"{self.subject_prefix} {message.title}"
        mail["From"] = self.from_addr or ""
        mail["To"] = ", ".join(self.to_addrs)
        mail.set_content(message.body)

        try:
            if self.use_ssl:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=20) as smtp:
                    self._auth(smtp)
                    smtp.send_message(mail)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                    if self.use_starttls:
                        smtp.starttls()
                    self._auth(smtp)
                    smtp.send_message(mail)
        except NotifyError:
            raise
        except Exception as exc:  # noqa: BLE001 —— 统一转成发送错误，避免泄露底层细节
            raise NotifyError(f"SMTP 发送失败: {exc}") from exc

    def _auth(self, smtp: smtplib.SMTP) -> None:
        """有用户名则登录；口令解密失败直接抛出。"""
        if not self.username:
            return
        if not self._secret:
            raise NotifyError("SMTP 渠道缺少口令")
        try:
            smtp.login(self.username, self._secret)
        except smtplib.SMTPAuthenticationError as exc:
            raise NotifyError(f"SMTP 认证失败: {exc}") from exc
