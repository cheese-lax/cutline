# Security Policy

## Supported versions

安全修复面向默认分支的最新源码。发布标签用于可重复下载，不承诺为旧标签提供独立维护。

## Localhost security boundary

本项目是单用户 localhost 工具。服务应只绑定 `127.0.0.1` 或 `::1`，不得直接暴露到局域网或互联网，也不应由公开反向代理转发。启动时生成的访问令牌、Host/Origin 校验和浏览器安全响应头属于必要保护。

项目会处理用户选择的本地图片并写入本地输出目录。请只处理可信文件，并使用普通用户权限运行；不要以管理员或 root 权限启动。

## Reporting a vulnerability

请不要在公开 Issue 中披露尚未修复的漏洞。优先通过 GitHub 仓库的 **Security → Advisories → Report a vulnerability** 私密报告，并提供：

- 受影响的提交或版本；
- 复现步骤和最小样例；
- 实际影响与预期行为；
- 已验证的平台和 Python 版本。

如果仓库尚未启用私密漏洞报告，请联系仓库维护者并只发送最少必要信息，等待安全沟通渠道确认后再传输完整复现材料。
