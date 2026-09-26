"""Explicit-path local runtime for embedding inside the existing host backend.

No HTTP server, sys.path mutation, cwd change, credential file or import-time
I/O. Assets are a checksummed deployment snapshot, state is host-owned. The
runtime is single-flight; the host owns its bounded admission queue.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from collections import OrderedDict
from pathlib import Path

from app.services.rag_engine.config import resolve_generation_config
from app.services.rag_engine.indexing.index_spec import get_index_spec, verify_index_identity
from app.services.rag_engine.indexing.vector_index import create_embedding_client, load_model_config
from app.services.rag_engine.llm.budget import resolve_counter
from app.services.rag_engine.llm.grounding_review import REVIEW_VERSION, review_result, withheld
from app.services.rag_engine.llm.local_generator import GenerationCancelled, LocalOllamaGenerator
from app.services.rag_engine.parsing.heading_rules import load_rules
from app.services.rag_engine.retrieval.execution_policy import assert_endpoint_allowed
from app.services.rag_engine.retrieval.evidence import EvidenceError, load_source
from app.services.rag_engine.service import ServiceDeps, locate_and_explain

RUNTIME_VERSION = "host-local-v2"
INDEX_SPEC = "active-p8d-v3"
#: 产品声明的四科；未指定学科时只在这四科册内检索（见 host_runtime.yaml）
PRODUCT_SUBJECTS = ("数学", "物理", "化学", "生物")


def verify_assets(assets_root: Path, *, full: bool = True) -> dict:
    root = Path(assets_root).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("runtime_version") != RUNTIME_VERSION:
        raise ValueError("教材引擎资产版本不匹配")
    members = manifest.get("members")
    if not isinstance(members, dict) or not members:
        raise ValueError("教材引擎资产清单为空")
    for rel, expected in members.items():
        target = (root / rel).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError("教材引擎资产缺失或路径越界")
        if full and hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError("教材引擎资产指纹不一致")
    required = {"configs/models.yaml", "configs/heading_rules.yaml", "configs/index_specs.yaml", "configs/host_runtime.yaml",
                "data/derived/tokenizer/qwen2_5_7b_gguf_vocab.json",
                "data/derived/p8d-v3/chunks_indexed.jsonl"}
    if not required.issubset(members):
        raise ValueError("教材引擎资产清单不完整")
    return manifest


def probe_runtime(assets_root: Path) -> dict:
    """Lightweight readiness, not a quality certificate; does not run inference."""
    try:
        import httpx
        import jieba  # noqa: F401
        import jinja2  # noqa: F401
        import rank_bm25  # noqa: F401
        verify_assets(assets_root, full=True)
        config = load_model_config(Path(assets_root) / "configs/models.yaml")
        rules = load_rules(Path(assets_root) / "configs/heading_rules.yaml")
        if not Path(rules.corpus_root).is_dir():
            raise ValueError("教材原文目录不可用")
        gen = resolve_generation_config(config)
        emb = config["embedding"]["providers"][config["embedding"]["active"]]
        for spec in (gen, emb):
            if spec["provider"] != "local-ollama":
                raise ValueError("教材引擎只支持本地模型")
            endpoint = spec["tags_endpoint"]
            assert_endpoint_allowed(endpoint, "local-only", name="tags")
            with httpx.Client(timeout=3, follow_redirects=False, trust_env=False) as client:
                response = client.get(endpoint)
                response.raise_for_status()
            models = response.json()["models"]
            name = spec["model"]
            actual = next((m for m in models if m.get("name") in {name, name + ":latest"}), None)
            if not actual or actual.get("digest", "").removeprefix("sha256:") != str(
                    spec["expected_manifest_digest"]).removeprefix("sha256:"):
                raise ValueError("本地教材模型缺失或版本不匹配")
        return {"available": True, "detail": "本地教材引擎可用；四科定位与依据核验。",
                "human_quality": "not_run", "runtime_version": RUNTIME_VERSION}
    except Exception as exc:
        # Paths, model responses, and arbitrary exception text stay out of UI.
        return {"available": False, "detail": "本地教材引擎未就绪，请检查教材资产与 Ollama 模型。",
                "reason": type(exc).__name__, "human_quality": "not_run"}


class LocalRagRuntime:
    def __init__(self, *, assets_root: Path, state_root: Path):
        self.assets_root = Path(assets_root).resolve()
        self.state_root = Path(state_root).resolve()
        if self.state_root == self.assets_root or self.state_root.is_relative_to(self.assets_root):
            raise ValueError("运行状态必须与只读教材资产分离")
        self.manifest = verify_assets(self.assets_root)
        if not probe_runtime(self.assets_root)["available"]:
            raise ValueError("教材资产或本地模型身份核验失败")
        self.config = load_model_config(self.assets_root / "configs/models.yaml")
        self.rules = load_rules(self.assets_root / "configs/heading_rules.yaml")
        import yaml
        product = yaml.safe_load((self.assets_root / "configs/host_runtime.yaml").read_text(encoding="utf-8"))
        self.subject_selectors = product["subject_selectors"]
        if product["version"] != RUNTIME_VERSION or set(self.subject_selectors) != {"数学", "物理", "化学", "生物"}:
            raise ValueError("产品教材范围配置不匹配")
        self.gen_config = resolve_generation_config(self.config)
        if self.gen_config["provider"] != "local-ollama":
            raise ValueError("生成器必须为本地模型")
        self.gen_config["timeout_seconds"] = min(self.gen_config["timeout_seconds"], 60)
        self.config = copy.deepcopy(self.config)
        emb = self.config["embedding"]["providers"][self.config["embedding"]["active"]]
        emb["timeout_seconds"] = min(emb["timeout_seconds"], 30)
        emb["retry"]["max_retries"] = 0
        self.usage_log = self.state_root / "api_usage.jsonl"
        self.embedding = create_embedding_client(self.config, execution_policy="local-only",
                                                  usage_log=self.usage_log)
        self.generator = LocalOllamaGenerator(self.gen_config, policy="local-only",
                                              usage_log=self.usage_log)
        self.identity = get_index_spec(INDEX_SPEC, self.assets_root / "configs/index_specs.yaml",
                                       base_dir=self.assets_root)
        self.snapshot, self.index_meta = verify_index_identity(
            self.identity, dim=1024, model_ns=self.embedding.model_ns,
            model_id=self.embedding.model_id, tag="cch", session_cache=False)
        self.vocab_path = self.assets_root / "data/derived/tokenizer/qwen2_5_7b_gguf_vocab.json"
        self.counter, reason = resolve_counter(model_manifest_digest=self.gen_config["expected_manifest_digest"],
                                               vocab_path=self.vocab_path)
        if self.counter is None:
            raise ValueError("精确上下文计数器不可用")
        self._lock = threading.Lock()
        self._closed = False
        self._results = OrderedDict()

    def _provider(self, subject):
        if subject is not None and subject not in self.subject_selectors:
            raise ValueError("教材引擎当前仅支持数学、物理、化学、生物")
        if subject:
            searcher = self.snapshot.searcher_for(tuple(self.subject_selectors[subject]),
                                                  warm_bm25=True)
            route = {"scope": "subject", "subject_filter": subject}
        else:
            # 未指定学科 ≠ 全库：产品只声明四科，未声明册不得作为"教材原文"发布。
            # 索引本身仍保留全库（历史评测口径不变），过滤发生在检索空间选择上。
            searcher = self.snapshot.searcher_for_selectors(
                tuple(tuple(self.subject_selectors[name]) for name in PRODUCT_SUBJECTS),
                warm_bm25=True)
            route = {"scope": "product", "subject_filter": None,
                     "product_subjects": list(PRODUCT_SUBJECTS)}
        return searcher, {**self.index_meta, **route,
                          "n_chunks": len(searcher.body), "session_snapshot": True}

    def _prune_results(self):
        now = time.monotonic()
        for key, (created, _, _) in list(self._results.items()):
            if now - created >= 600:
                del self._results[key]

    def prune_cache(self):
        """Host janitor may evict idle user text without waiting for inference."""
        if self._lock.acquire(blocking=False):
            try:
                self._prune_results()
            finally:
                self._lock.release()

    def locate(self, question: str, *, subject: str | None = None, cancel_token=None) -> dict:
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError("题目须为 1–4000 字符")
        if self._closed:
            raise RuntimeError("教材引擎已关闭")
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("教材引擎正在处理其他请求")
        started = time.monotonic()
        try:
            self._prune_results()
            if cancel_token is not None and cancel_token.is_set():
                raise GenerationCancelled("请求已取消")
            self.generator.cancel_token = cancel_token
            # Runtime keeps user text only in bounded, short-lived memory.
            # A reconnect is additionally bound to the host turn/event history.
            key = hashlib.sha256(json.dumps([RUNTIME_VERSION, REVIEW_VERSION, question, subject],
                                            ensure_ascii=False).encode()).hexdigest()
            cached = self._results.get(key)
            if cached is not None:
                timestamp, previous, sources = cached
                valid = time.monotonic() - timestamp < 600
                for file, sha in sources:
                    try:
                        valid = valid and load_source(file, self.rules.corpus_root).sha256 == sha
                    except (OSError, EvidenceError):
                        valid = False
                if valid:
                    if cancel_token is not None and cancel_token.is_set():
                        raise GenerationCancelled("请求已取消，缓存结果不采用")
                    result = copy.deepcopy(previous)
                    result["provenance"]["local_inference_count"] = 0
                    result["provenance"]["runtime"]["result_cache_hit"] = True
                    result["provenance"]["runtime"]["seconds"] = round(time.monotonic() - started, 3)
                    self._results.move_to_end(key)
                    return result
                self._results.pop(key, None)

            # The direct query endpoint cannot bypass model identity checking.
            if not probe_runtime(self.assets_root)["available"]:
                raise ValueError("教材资产或本地模型身份核验失败")

            def embed(text):
                if cancel_token is not None and cancel_token.is_set():
                    raise GenerationCancelled("请求已取消")
                return self.embedding.embed([text], dim=1024, purpose="host_query")[0]

            deps = ServiceDeps(searcher_provider=self._provider, embed_query=embed,
                generator=self.generator, corpus_root=self.rules.corpus_root,
                cache_dir=None, generation_config=self.gen_config, runs_dir=None,
                tokenizer_vocab_path=str(self.vocab_path), strict_identity=True,
                candidate_id=f"{RUNTIME_VERSION}:{REVIEW_VERSION}")
            base = locate_and_explain(question, deps=deps, subject=subject).to_dict()
            if cancel_token is not None and cancel_token.is_set():
                raise GenerationCancelled("请求已取消，结果不采用")
            result = review_result(base, generator=self.generator, config=self.gen_config,
                                   counter=self.counter, corpus_root=self.rules.corpus_root,
                                   cancel_token=cancel_token)
            if cancel_token is not None and cancel_token.is_set():
                raise GenerationCancelled("请求已取消，结果不采用")
            result["provenance"]["runtime"] = {"version": RUNTIME_VERSION,
                "seconds": round(time.monotonic() - started, 3), "human_quality": "not_run",
                "result_cache_hit": False, "cache_scope": "memory_ttl600_capacity64"}
            if result["status"] in {"ok", "uncertain"} or (
                    result["status"] == "partial" and result["explanations"]):
                sources = {(s["file"], s["source_sha256"]) for s in base["evidence"]}
                self._results[key] = (time.monotonic(), copy.deepcopy(result), sources)
                self._results.move_to_end(key)
                while len(self._results) > 64:
                    self._results.popitem(last=False)
            return result
        finally:
            self.generator.cancel_token = None
            self._lock.release()

    def probe(self) -> dict:
        return probe_runtime(self.assets_root)

    def close(self) -> None:
        self._closed = True
        self._results.clear()
        self.generator.close()
        if self.embedding._client is not None:
            self.embedding._client.close()
