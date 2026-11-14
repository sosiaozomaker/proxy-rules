#!/usr/bin/env python3
"""Validate Claude rule-provider format, uniqueness, and domain matching.

This is a local check. It does not log in to Claude or send any messages.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML is required: python3 -m pip install pyyaml\n")
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rules" / "claude.yaml"
EXAMPLE = ROOT / "examples" / "openclash-mihomo-snippet.yaml"

# behavior: domain payload must be clash domain wildcards, not classical rules.
CLASSICAL_PREFIX = re.compile(
    r"^(DOMAIN-SUFFIX|DOMAIN-KEYWORD|DOMAIN-WILDCARD|DOMAIN|IP-CIDR|"
    r"IP-CIDR6|GEOIP|GEOSITE|SRC-IP-CIDR|DST-PORT|SRC-PORT|PROCESS-NAME)\s*,",
    re.IGNORECASE,
)
DOMAIN_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
APEX_RE = re.compile(rf"^\+\.({DOMAIN_LABEL}(?:\.{DOMAIN_LABEL})+)$", re.IGNORECASE)

# Hosts documented by official Anthropic / Claude pages at the time of writing.
MUST_MATCH = [
    "claude.ai",
    "www.claude.ai",
    "claude.com",
    "www.claude.com",
    "platform.claude.com",
    "support.claude.com",
    "code.claude.com",
    "status.claude.com",
    "anthropic.com",
    "www.anthropic.com",
    "api.anthropic.com",
    "console.anthropic.com",
    "mail.anthropic.com",
]

# Must not steal unrelated or third-party traffic.
MUST_NOT_MATCH = [
    "google.com",
    "www.google.com",
    "accounts.google.com",
    "cloudflare.com",
    "challenges.cloudflare.com",
    "github.com",
    "raw.githubusercontent.com",
    "intercom.io",
    "stripe.com",
    "example.com",
    "notclaude.ai",
    "claude.ai.example.com",
    "anthropic.com.example.com",
    "myclaude.com",
    "claude.ai.com",
]


def clash_plus_match(pattern: str, host: str) -> bool:
    """Match Mihomo '+.example.com' wildcard (suffix including the apex)."""
    if not pattern.startswith("+."):
        raise ValueError(f"unsupported test pattern: {pattern}")
    apex = pattern[2:].lower().rstrip(".")
    host = host.lower().rstrip(".")
    return host == apex or host.endswith("." + apex)


def load_payload(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "payload" not in data:
        raise SystemExit(f"{path}: missing top-level payload")
    payload = data["payload"]
    if not isinstance(payload, list) or not payload:
        raise SystemExit(f"{path}: payload must be a non-empty list")
    return [str(item).strip() for item in payload]


def validate_rules() -> list[str]:
    errors: list[str] = []
    payload = load_payload(RULES)

    seen: set[str] = set()
    for item in payload:
        if not item:
            errors.append("empty payload entry")
            continue
        if CLASSICAL_PREFIX.match(item):
            errors.append(
                f"{item!r} looks like classical syntax; domain behavior needs '+.example.com'"
            )
            continue
        if item in seen:
            errors.append(f"duplicate payload entry: {item}")
        seen.add(item)
        if APEX_RE.match(item) is None:
            errors.append(f"{item!r} is not a quoted-style '+.<domain>' apex wildcard")

    expected = {"+.claude.ai", "+.claude.com", "+.anthropic.com"}
    if set(payload) != expected:
        errors.append(f"payload {payload!r} does not equal expected {sorted(expected)}")

    for host in MUST_MATCH:
        if not any(clash_plus_match(p, host) for p in payload):
            errors.append(f"expected official host to match: {host}")

    for host in MUST_NOT_MATCH:
        hits = [p for p in payload if clash_plus_match(p, host)]
        if hits:
            errors.append(f"host {host} unexpectedly matched {hits}")

    # Secret / private-data leakage guards on the public files we ship.
    public_files = [
        RULES,
        EXAMPLE,
        ROOT / "README.md",
    ]
    forbidden = re.compile(
        r"(?i)(\bsk-[a-z0-9_-]{10,}\b|\buuid\b\s*[:=]|-----BEGIN|"
        r"\b(api[_-]?token|secret|password)\s*[:=]\s*\S+)"
    )
    # Do not publish literal public server IPs either.
    ipv4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b")
    allow_ip_context = {"127.0.0.1", "0.0.0.0"}
    for path in public_files:
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            errors.append(f"{path.name}: looks like it may contain a secret pattern")
        for match in ipv4.finditer(text):
            ip = match.group(0)
            if ip not in allow_ip_context:
                # Documentation may mention IPv4 as a concept; reject dotted addresses.
                errors.append(f"{path.name}: unexpected IPv4 address {ip}")

    example = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    provider = (example or {}).get("rule-providers", {}).get("claude", {})
    required = {
        "type": "http",
        "behavior": "domain",
        "format": "yaml",
        "interval": 86400,
        "path": "./rule_provider/claude.yaml",
        "url": "https://raw.githubusercontent.com/sosiaozomaker/proxy-rules/main/rules/claude.yaml",
    }
    for key, value in required.items():
        if provider.get(key) != value:
            errors.append(f"example rule-providers.claude.{key} should be {value!r}, got {provider.get(key)!r}")

    rules = example.get("rules") or []
    if "RULE-SET,claude,Claude-LisaHost" not in rules:
        errors.append("example must contain RULE-SET,claude,Claude-LisaHost")
    else:
        idx = rules.index("RULE-SET,claude,Claude-LisaHost")
        later = rules[idx + 1 :]
        if not any(str(r).startswith("MATCH,") or str(r).startswith("GEOIP,") for r in later):
            errors.append("example should show RULE-SET placed before MATCH/broad rules")
        if any(str(r).startswith("MATCH,") or str(r).startswith("GEOIP,") for r in rules[:idx]):
            errors.append("example has MATCH/GEOIP before RULE-SET")

    return errors


def main() -> int:
    errors = validate_rules()
    if errors:
        print("FAIL")
        for item in errors:
            print(f"- {item}")
        return 1
    print("OK: rules/claude.yaml format, uniqueness, and domain matching")
    print("OK: example snippet fields and RULE-SET order")
    return 0


if __name__ == "__main__":
    sys.exit(main())
