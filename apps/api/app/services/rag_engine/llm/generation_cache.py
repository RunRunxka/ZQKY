"""P7 生成缓存（docs/SCHEMA.md §十）。

路径：``<cache_dir>/<model_ns>/v<cache_contract_version>/<key[:2]>/<key>.json``
键 = sha256(规范化 JSON)，载荷含（**全部身份字段，任一变化 → 键不同**）：
  question + constraints + 证据 [(citation_id, text_sha256)...]（**顺序参与**） +
  prompt_version + schema_version + provider + model_id + manifest digest +
  num_ctx + temperature + seed + num_predict。
  P11 第二步：影子候选在载荷里**额外**带上 `candidate_id` + `index_spec`
  （只在显式给值时进入载荷；现役默认路径的载荷逐字节不变）。

物理隔离：mock 生成器与真实本地缓存走**不同命名空间**（model_ns 不同目录），
mock 记录一律带 ``mock: true``，防止 mock 产物被真实链路复用。

写盘：唯一临时文件 + os.replace；**错误/取消不写**（写不写由调用方决定）。
合法拒答也是可复放的语义结果，服务通过 result_policy 显式隔离新旧缓存语义。
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

#: P8A 升版到 2：服务边界改为严格 schema 校验（R6）。键里的 schema_version
#: 已随之变为 p7-v2，本版本号进一步把旧 v1 命名空间物理隔离（历史记录保留在
#: 磁盘，不再读取），避免"旧的不合格缓存继续返回 ok"。
#: P8C 升版到 3：键载荷新增 `answer_policy`（P8C-2 A2 回答策略候选）——**影响发给模型的
#: 系统提示词**，因此必须进入键，否则 A/B 两臂会互相串缓存。v2 记录保留在磁盘不再读取。
CACHE_CONTRACT_VERSION = 3

# 独立于磁盘格式版本：旧 A0 键仍可复算，当前服务只读取含此身份的新记录。
# 该策略缓存经 schema/引用/源复验通过的回答和拒答，不缓存部分失败。
CACHE_RESULT_POLICY = "validated-semantic-outcome-v1"


class GenerationCache:
    """生成结果缓存。命名空间由 provider/model_id 决定（mock 物理隔离）。"""

    def __init__(self, cache_dir: str | Path, model_ns_name: str,
                 contract_version: int = CACHE_CONTRACT_VERSION):
        self.root = Path(cache_dir) / model_ns_name / f"v{contract_version}"
        self.model_ns = model_ns_name
        self.contract_version = int(contract_version)

    # ---- 键 ----

    @staticmethod
    def build_key_payload(*, question: str, constraints: dict,
                          evidence: list[tuple[str, str]], prompt_version: str,
                          schema_version: str, provider: str, model_id: str,
                          manifest_digest: str | None, num_ctx: int,
                          temperature: float, seed: int, num_predict: int,
                          answer_policy: str = "baseline",
                          candidate_id: str | None = None,
                          index_spec: str | None = None,
                          result_policy: str | None = None) -> dict:
        """缓存键载荷。evidence = [(citation_id, text_sha256)...]，顺序参与哈希。

        `answer_policy` 自 v3 起参与键：它改变系统提示词（模型实际看到的内容），
        必须与 prompt_version/schema_version 一起构成"提示词身份"。

        `candidate_id` / `index_spec`（P11 第二步）：**只在显式给值时进入载荷**。
        影子候选必须与 A0 的键物理可分——否则候选 A 会直接复用 A0 缓存，三个候选
        之间也不可分（登记要求：键须含 index_spec + 模型身份 + 提示版本/候选 ID）。
        未给值时（现役默认路径）载荷**逐字节不变** → A0 历史缓存键可继续复算、
        历史缓存文件保留。服务显式传 result_policy，区分只缓存回答的旧语义与
        同时缓存合法拒答的新语义；未传时仍可复算历史键。
        """
        payload = {
            "cache_contract_version": CACHE_CONTRACT_VERSION,
            "question": question,
            "constraints": constraints,
            "evidence": [[cid, sha] for cid, sha in evidence],
            "prompt_version": prompt_version,
            "schema_version": schema_version,
            "answer_policy": str(answer_policy),
            "provider": provider,
            "model_id": model_id,
            "manifest_digest": manifest_digest,
            "num_ctx": int(num_ctx),
            "temperature": float(temperature),
            "seed": int(seed),
            "num_predict": int(num_predict),
        }
        if candidate_id is not None:
            payload["candidate_id"] = str(candidate_id)
        if index_spec is not None:
            payload["index_spec"] = str(index_spec)
        if result_policy is not None:
            payload["result_policy"] = str(result_policy)
        return payload

    @staticmethod
    def make_key(payload: dict) -> str:
        norm = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    # ---- 路径 ----

    def path_for(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    # ---- 读 ----

    def get(self, key: str) -> dict | None:
        """命中返回记录；缺失/损坏/契约版本不符 → None（不静默使用坏记录）。"""
        p = self.path_for(key)
        if not p.exists():
            return None
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(rec, dict):
            return None
        if rec.get("cache_contract_version") != self.contract_version:
            return None
        if rec.get("key") != key:
            return None
        if rec.get("output") is None or rec.get("raw_response") is None:
            return None
        return rec

    # ---- 写 ----

    def put(self, key: str, payload_identity: dict, output: dict, raw_response: str,
            usage: dict, *, mock: bool) -> dict:
        """已校验的语义结果原子落盘。**错误/取消不得调用本方法**（调用方保证）。

        记录含完整键载荷（审计可复算）、输出对象、原始响应、usage、mock 标记与 ts。
        """
        record = {
            "cache_contract_version": self.contract_version,
            "key": key,
            "identity": payload_identity,
            "output": output,
            "raw_response": raw_response,
            "usage": usage,
            "mock": bool(mock),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        p = self.path_for(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        # 固定 <key>.tmp 会让同键并发写互相覆盖/移动临时文件，甚至抛
        # FileNotFoundError。每个写入者独占临时文件；读者只看到完整 JSON。
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", newline="\n",
                    dir=p.parent, prefix=f".{key}.", suffix=".tmp",
                    delete=False) as handle:
                tmp = Path(handle.name)
                json.dump(record, handle, ensure_ascii=False, indent=1)
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(7):
                try:
                    os.replace(tmp, p)
                    break
                except PermissionError as e:
                    # Windows 同键 replace/短暂读句柄竞争会报 access/sharing
                    # violation。仅重试这一小类错误，最多等待 315ms；其他
                    # I/O 错误或持续不可写照常抛出，不假装缓存已成功。
                    if getattr(e, "winerror", None) not in (5, 32, 33) or attempt == 6:
                        raise
                    time.sleep(0.005 * (2 ** attempt))
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
        return record
