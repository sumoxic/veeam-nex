"""Veeam VBR 接入层。

- client    —— REST 客户端（OAuth2、自动续期、401 自愈重试）
- collector —— 数据采集（含翻页与 VBR 时钟基准）
- rules     —— 规则目录
- checks    —— 规则实现
- engine    —— 规则执行
- operations—— 远程操作端点映射
"""
