"""执行策略与网络边界守卫（P5-LOCAL 契约，总控定义，单一定义点）。

三态策略（`configs/models.yaml` 的 `execution.policy`；CLI `--execution-policy` 可覆盖）：

- ``local-only``（**本批默认**）：
    * 允许 **进程内/子进程本地模型推理**（如本地 rerank worker：无任何网络）；
    * 允许**显式配置的本机回环端点**（host 必须是 ``127.0.0.1``/``::1``/``localhost``，
      且必须带显式 scheme/port）；
    * **禁止**云端 provider、任何非回环主机、任何依赖 DNS 的主机名（含"看起来像本地"的域名）、
      带 userinfo 的 URL（``http://127.0.0.1@evil.com`` 这类逃逸）、以及重定向跟随。
- ``cache-only``：**禁止一切网络**（含本机回环 Ollama）。只读本地缓存，缺失即失败。
  该语义与 P5A 完全一致，回归测试必须继续通过。
- ``cloud-allowed``：仅在**显式选择**时允许云端 provider（如 zhipu）。默认配置不得是它。

设计要点：local-only 是**独立策略**，不是"auto + 默认 URL 是本地"——它主动拒绝云端
provider 与远程 URL，并把校验做在创建客户端之前（失败早于任何 I/O）。

残留风险（必须在文档中如实说明）：回环端点理论上可能被同机转发代理冒充。
本项目的应对是组合证据：① 端点必须是回环 + 显式端口；② 本地模型 digest 与登记值比对
（见 :func:`verify_local_model_digest_hint`）；③ **断网运行仍成功**的实测证据；
④ 评分缓存记录模型 revision。四者合起来才能声称"真实本地推理"。
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

POLICY_LOCAL_ONLY = "local-only"
POLICY_CACHE_ONLY = "cache-only"
POLICY_CLOUD_ALLOWED = "cloud-allowed"
POLICIES = (POLICY_LOCAL_ONLY, POLICY_CACHE_ONLY, POLICY_CLOUD_ALLOWED)
DEFAULT_POLICY = POLICY_LOCAL_ONLY

#: provider 种类 → 允许的策略集合。provider 种类来自 configs/models.yaml 的 spec["provider"]。
PROVIDER_KINDS = ("zhipu", "local-ollama", "local-worker", "mock")
ALLOWED_KINDS_BY_POLICY = {
    POLICY_LOCAL_ONLY: frozenset({"local-ollama", "local-worker", "mock"}),
    POLICY_CACHE_ONLY: frozenset(),          # 缓存模式不允许任何可发起 I/O 的 provider 实现
    POLICY_CLOUD_ALLOWED: frozenset(PROVIDER_KINDS),
}


class PolicyViolation(RuntimeError):
    """违反执行策略（云端 provider / 远程 URL / 重定向逃逸 / 非法主机）。"""


def normalize_policy(policy: str | None) -> str:
    if policy is None or policy == "":
        return DEFAULT_POLICY
    if policy not in POLICIES:
        raise PolicyViolation(f"未知执行策略 {policy!r}，允许：{POLICIES}")
    return policy


def is_loopback_url(url: str) -> bool:
    """仅接受字面回环主机：IP 字面量必须 is_loopback，或主机名恰为 localhost。

    **不做 DNS 解析**——任何需要解析的主机名在 local-only 下都不被信任。
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.hostname
    if not host:
        return False
    # userinfo（user@host）一律拒绝：可能被用来伪装目标主机
    if "@" in (parts.netloc or ""):
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def assert_provider_allowed(provider_kind: str, policy: str, *, name: str = "") -> None:
    """按策略校验 provider 种类；不允许即抛 PolicyViolation。"""
    policy = normalize_policy(policy)
    allowed = ALLOWED_KINDS_BY_POLICY[policy]
    if provider_kind not in allowed:
        label = f"{name!r} " if name else ""
        raise PolicyViolation(
            f"执行策略 {policy} 不允许 {label}provider={provider_kind!r}"
            f"（允许：{sorted(allowed) or '无'}）。云端 provider 需显式 --execution-policy cloud-allowed。")


def assert_endpoint_allowed(url: str | None, policy: str, *, name: str = "") -> None:
    """按策略校验端点 URL。

    local-only：端点必须存在且是回环 URL（本机推理端点的唯一合法形态）。
    cloud-allowed：不做主机限制（仍禁止 userinfo 伪装）。
    cache-only：不接受任何端点。
    """
    policy = normalize_policy(policy)
    label = f"{name!r} " if name else ""
    if policy == POLICY_CACHE_ONLY:
        raise PolicyViolation(f"执行策略 cache-only 禁止任何端点（{label}url={url!r}）")
    if url is None:
        if policy == POLICY_LOCAL_ONLY:
            raise PolicyViolation(f"执行策略 local-only 要求 {label}显式给出回环端点；缺省端点不被信任")
        return
    if url and "@" in (urlsplit(url).netloc or ""):
        raise PolicyViolation(f"{label}端点含 userinfo，疑似逃逸：{url!r}")
    if policy == POLICY_LOCAL_ONLY and not is_loopback_url(url):
        raise PolicyViolation(
            f"执行策略 local-only 只允许回环端点，得到 {label}url={url!r}"
            f"（主机必须为 127.0.0.1/::1/localhost，且不做 DNS 解析）")


def assert_no_redirect_follow(follow_redirects: bool, policy: str) -> None:
    """禁止靠重定向把回环请求转发到远端。"""
    if normalize_policy(policy) in (POLICY_LOCAL_ONLY, POLICY_CACHE_ONLY) and follow_redirects:
        raise PolicyViolation("本策略下禁止跟随重定向（防止回环→远端逃逸）")


def check_local_model_digest(hint: dict, expected: dict) -> None:
    """比对本地服务报告的模型身份与登记值（如 Ollama /api/tags 的 digest）。

    hint 至少含 ``model``（名字）；``digest``/``model_digest`` 任一与 expected 的对应键
    不等即报错。expected 为空（未登记）时只做存在性检查，并由调用方在报告里记
    ``identity_verified=False``——不得伪填。
    """
    if not hint:
        raise PolicyViolation("本地服务未返回模型身份信息，无法确认使用的是本地权重")
    exp_name = expected.get("model")
    if exp_name and hint.get("model") not in (exp_name, None):
        if exp_name not in str(hint.get("model", "")):
            raise PolicyViolation(f"本地服务模型名不符：报告 {hint.get('model')!r}，登记 {exp_name!r}")
    for key in ("digest", "model_digest"):
        exp = expected.get(key)
        got = hint.get(key)
        if exp and got and str(got) != str(exp):
            raise PolicyViolation(f"本地模型 {key} 与登记值不符：{got!r} != {exp!r}（可能是别的模型/代理）")
