# proxy-rules

面向 OpenWrt 上 OpenClash / Mihomo 的**公共纯规则仓库**。当前提供一套 Claude 登录、OAuth 与 Claude Code 所用的官方域名规则，方便多台路由器用同一条订阅，把这些域名走到你在本地配置的策略组（示例名 `Claude-LisaHost`）。

本仓库**只含通用公开规则、说明与示例/测试**，不含任何节点配置、IP 与端口、UUID、密钥、token、私人域名、账户或日志。

规则列表来自撰写时能核对到的官方公开文档与状态页，**不保证永远完整**。官方若改用新的一级域名，需要再更新本仓库。

## 订阅地址

规则文件：

- 仓库路径：[`rules/claude.yaml`](https://github.com/sosiaozomaker/proxy-rules/blob/main/rules/claude.yaml)
- Raw：https://raw.githubusercontent.com/sosiaozomaker/proxy-rules/main/rules/claude.yaml

## 规则格式

文件使用 Mihomo / Clash Meta 的 `behavior: domain`，payload 为 clash 域名通配，而不是 `classical` 的 `DOMAIN-SUFFIX,...` 写法。两者必须保持一致：若改用 `classical`，payload 才应写成 `DOMAIN-SUFFIX,claude.ai` 这种形式。

当前条目：

| payload | 含义（等价 classical） | 会匹配的官方主机示例 |
| --- | --- | --- |
| `+.claude.ai` | `DOMAIN-SUFFIX,claude.ai` | `claude.ai`、`www.claude.ai` |
| `+.claude.com` | `DOMAIN-SUFFIX,claude.com` | `claude.com`、`platform.claude.com`、`support.claude.com`、`code.claude.com`、`status.claude.com` |
| `+.anthropic.com` | `DOMAIN-SUFFIX,anthropic.com` | `anthropic.com`、`api.anthropic.com`、`console.anthropic.com` |

`+.example.com` 会匹配 `example.com` 本身以及所有子域，参见 [Mihomo Syntax：Domain Wildcards](https://wiki.metacubex.one/en/handbook/syntax/#domain-wildcards)。

收录依据（官方来源，撰写时核对）：

- [Log in to your Claude account](https://support.claude.com/en/articles/13189465-log-in-to-your-claude-account)：网页登录在 `claude.ai`；登录邮件来自 `@mail.anthropic.com`
- [Claude Code Authentication](https://code.claude.com/docs/en/authentication)：使用 `claude.ai` 账户登录；定价页为 `claude.com/pricing`；Console 在 `platform.claude.com`
- [Claude API overview](https://platform.claude.com/docs/en/api/overview)：API 位于 `https://api.anthropic.com`
- [Claude Status](https://status.claude.com/)：列出 `claude.ai`、`platform.claude.com`、`api.anthropic.com` 等组件

## 本地配置要点

节点必须是 **Mihomo 兼容** 的本地配置。策略组与节点都在**每台路由器本地管理**，不要提交到本仓库。

在 Mihomo / OpenClash 配置中增加（完整语法示例见 [`examples/openclash-mihomo-snippet.yaml`](examples/openclash-mihomo-snippet.yaml)）：

```yaml
rule-providers:
  claude:
    type: http
    behavior: domain
    format: yaml
    interval: 86400
    path: ./rule_provider/claude.yaml
    url: https://raw.githubusercontent.com/sosiaozomaker/proxy-rules/main/rules/claude.yaml

rules:
  - RULE-SET,claude,Claude-LisaHost
```

- `RULE-SET,claude,Claude-LisaHost` **必须放在宽泛规则和 `MATCH` 之前**（也包括容易提前命中的 `GEOIP`、大范围 `GEOSITE` 等），否则这套规则可能不会生效。
- 策略组名称可按本地习惯修改，但要与 `RULE-SET` 第三段一致。
- **防回环**：若代理客户端会连接你的代理服务器本身，请在各路由器本地添加指向该服务器的 `DIRECT` 规则（`IP-CIDR` 或域名），并放在本 `RULE-SET` 之前。不要把具体服务器公网 IP 写进公共仓库。

## OpenClash 持久化

不要只改订阅自动生成的配置文件。更新或重新生成订阅后，那些改动通常会被覆盖。

请把 `rule-providers` 与对应的 `RULE-SET` 写进 OpenClash 的**自定义规则 / 配置覆写（overwrite）**里，确保重启和订阅更新后仍然保留。不同版本菜单名称可能略有差别，以你所用版本的「自定义 / 覆写」为准。

## DNS 模式与 IP 核验的局限

本规则集按**域名**匹配，不会按目的 IP 列表匹配。

- **fake-ip**：一般仍按查询时的域名命中；若关闭嗅探，且客户端直接对 IP 建连，可能绕过本规则。
- **redir-host**：依赖设备实际使用的 DNS 结果；DNS 未经过 Clash、结果被污染或应用自带解析时，可能漏匹配。
- 打开域名嗅探（sniff）有助于把 IP 连接还原成域名再匹配，但不能覆盖所有应用。
- 用访问 IP 查询站的方式核验出口，只能说明「这一次连接」走了哪个节点，**不能**证明所有 Claude 相关域名都已命中本规则。

## 明确不包含的流量

为避免把大量无关流量导向代理，本仓库**不会**加入整个 `google.com` 或 `cloudflare.com`。

因此：

- 若在 Claude 页面使用「Continue with Google」登录，Google 账号页不会被本规则覆盖。
- 部分站点的 Cloudflare 人机验证页面也不会被本规则覆盖。

这类第三方步骤请在本机既有分流里处理，或仅对确有需要的少数主机在**本地**补规则。不要为了图省事把 Google / Cloudflare 全站加进公共规则。登录邮件本身走的是邮件协议，也不在本 HTTP/HTTPS 域名规则范围内；邮件里的登录链接仍指向 `claude.ai`。

若实际使用中发现官方启用了新的一级域名，请核对官方文档后再考虑增补，不要把未经确认的追踪域名加进来。


## 本地测试

在仓库根目录用 Python 校验格式、重复项和域名通配（需要 PyYAML）：

```bash
python3 tests/validate_rules.py
```

也可用官方 Mihomo 对示例测试配置做语法检查（`-t` 只检查配置，不会登录 Claude 或发消息）：

```bash
mihomo -t -d . -f tests/mihomo-local-test.yaml
```

`tests/mihomo-local-test.yaml` 仅用于本地语法检查，通过 `type: file` 读取本仓库规则，不是可部署配置。

## 许可

规则与文档可自由使用、复制、修改和再发布。使用前请自行检查是否适合你的网络环境。
