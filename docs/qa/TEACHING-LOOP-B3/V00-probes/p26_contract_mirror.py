"""V00 · B3-C8 契约镜像逐字段对比（含本批新增字段）。

对比 `apps/api/app/contracts/scores.py` ↔ `apps/web/src/contracts/scores.ts`：
  模型集合、字段名（camelCase 别名）、必填/可选（默认值 ↔ `?`）、可空（`| None` ↔ `| null`）、
  类型类别（string/number/boolean/array/模型引用）、字面量枚举集合。
另对比两处本批新增/接线字段：
  - `AssessmentView.activeScoreRevisionId`（app/contracts/assessments.py ↔ web/contracts/assessments.ts）
  - `QuestionKnowledgeLinkView`（app/schemas/question_bank.py ↔ web/contracts/question-bank.ts）

**版本口径（r2 更新）**：本探针的初始版本（r1）断言"scores.ts 与 scores.py 差集 = 已披露的
ScoreImportPatchRequest"，其结果记录在 `V00-REPORT-01.md`。r2 把 `ScoreImportPatchRequest`
并入 `contracts/scores.ts` 后，本文件已改为断言**差集为空**，并检查
`services/assessments-api.ts` 只从契约导入/再导出、不再持有第二份形状。

TS 侧用仓库自带 typescript 编译器解析（非正则）。运行（仓库根或 apps/api 均可）：
  apps/api/.venv/Scripts/python.exe -X utf8 <abs>/p26_contract_mirror.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import types
import typing
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import b3lib as B  # noqa: E402

CONTRACTS = B.API_DIR / "app" / "contracts"
SCHEMAS = B.API_DIR / "app" / "schemas"
WEB_CONTRACTS = B.REPO / "apps" / "web" / "src" / "contracts"
NODE_EXTRACT = HERE / "_mirror_ts_extract.cjs"


def ts_parse(files: list[Path]) -> dict:
    result = subprocess.run(
        ["node", str(NODE_EXTRACT), *[str(f) for f in files]],
        cwd=str(B.REPO),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def py_fields(model: type) -> dict[str, dict]:
    fields: dict[str, dict] = {}
    for name, field in model.model_fields.items():  # type: ignore[attr-defined]
        annotation = field.annotation
        nullable = _allows_none(annotation)
        fields[field.alias or name] = {
            "required": field.is_required(),
            "nullable": nullable,
            "kind": _kind(annotation),
            "annotation": str(annotation),
        }
    return fields


def _is_union(origin: object) -> bool:
    return origin is typing.Union or origin is types.UnionType


def _allows_none(annotation: object) -> bool:
    if annotation is type(None):
        return True
    origin = typing.get_origin(annotation)
    if _is_union(origin):
        return any(_allows_none(arg) for arg in typing.get_args(annotation))
    return False


def _kind(annotation: object) -> object:
    origin = typing.get_origin(annotation)
    if _is_union(origin):
        args = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        kinds = {_kind(arg) for arg in args}
        return sorted(kinds) if len(kinds) > 1 else (next(iter(kinds)) if kinds else "none")
    if origin is typing.Literal:
        return "enum:" + "|".join(sorted(str(v) for v in typing.get_args(annotation)))
    if origin is list:
        inner = typing.get_args(annotation)
        return "array<" + (_kind(inner[0]) if inner else "any") + ">"
    if annotation is str:
        return "string"
    if annotation is int:
        return "number(int)"
    if annotation is float:
        return "number(float)"
    if annotation is bool:
        return "boolean"
    if isinstance(annotation, type):
        return f"ref:{annotation.__name__}"
    return str(annotation)


#: TS 类型别名（如 ScoreStatus / ScoreImportState）→ kind，用于字段类型解析。
TS_ALIASES: dict[str, str] = {}


def register_aliases(ts_entries: dict) -> None:
    for name, entry in ts_entries.items():
        if entry.get("kind") == "alias":
            kind, _ = ts_kind(entry["type"])
            TS_ALIASES[name] = kind


def ts_kind(type_text: str) -> tuple[str, bool]:
    """TS 类型文本 → (kind, nullable)；kind 与 Python `_kind` 同构。"""
    text = type_text.strip()
    nullable = "null" in text
    if "|" in text and not text.endswith("[]"):
        parts = [
            part.strip()
            for part in text.split("|")
            if part.strip() and part.strip() not in ("null", "undefined")
        ]
        literals = [part for part in parts if re.fullmatch(r"'[^']*'", part)]
        if literals and len(literals) == len(parts):
            return ("enum:" + "|".join(sorted(part.strip("'") for part in literals)), nullable)
        kinds = sorted({ts_kind(part)[0] for part in parts})
        return (kinds[0] if len(kinds) == 1 else "|".join(kinds), nullable)
    if text.endswith("[]"):
        inner, _ = ts_kind(text[:-2])
        return (f"array<{inner}>", nullable)
    if text.startswith("Array<") and text.endswith(">"):
        inner, _ = ts_kind(text[6:-1])
        return (f"array<{inner}>", nullable)
    if re.fullmatch(r"'[^']*'", text):
        return ("enum:" + text.strip("'"), nullable)
    if text in ("string", "number", "boolean"):
        return (text, nullable)
    if text == "any":
        return ("any", nullable)
    if text in TS_ALIASES:
        return (TS_ALIASES[text], nullable)
    return (f"ref:{text}", nullable)


def compare_models(
    verdict: B.Verdict,
    *,
    label: str,
    py_models: dict[str, type],
    ts_entries: dict,
    ignore: set[str] | None = None,
    ts_scope: set[str] | None = None,
    known: dict[tuple[str, str, str], str] | None = None,
) -> None:
    known = known or {}
    ignore = ignore or set()
    py_names = sorted(set(py_models) - ignore)
    if ts_scope is not None:
        ts_names = sorted(
            name
            for name in ts_scope
            if name in ts_entries and ts_entries[name].get("kind") == "interface"
        )
    else:
        ts_names = sorted(
            name for name, entry in ts_entries.items() if entry.get("kind") == "interface"
        )
    verdict.expect(f"{label} 模型集合一致", py_names, ts_names)
    for name in py_names:
        if name not in ts_entries:
            continue
        py = py_fields(py_models[name])
        ts_members = {
            member["name"]: member for member in ts_entries[name]["members"]
        }
        verdict.expect(
            f"{label}.{name} 字段名集合",
            sorted(py),
            sorted(ts_members),
        )
        for field_name, meta in sorted(py.items()):
            member = ts_members.get(field_name)
            if member is None:
                continue
            ts_core, ts_nullable = ts_kind(member["type"])
            optional_key = (name, field_name, "optionality")
            if optional_key in known:
                if (not meta["required"]) != member["optional"]:
                    verdict.note(
                        f"[已登记镜像偏差] {label}.{name}.{field_name} 可选性：{known[optional_key]}"
                    )
                else:
                    verdict.expect(
                        f"{label}.{name}.{field_name} 可选性",
                        (not meta["required"]),
                        member["optional"],
                    )
            else:
                verdict.expect(
                    f"{label}.{name}.{field_name} 可选性（py required={meta['required']} ↔ ts optional={member['optional']}）",
                    (not meta["required"]),
                    member["optional"],
                )
            nullable_key = (name, field_name, "nullability")
            if nullable_key in known:
                if meta["nullable"] != ts_nullable:
                    verdict.note(
                        f"[已登记镜像偏差] {label}.{name}.{field_name} 可空性：{known[nullable_key]}"
                    )
                else:
                    verdict.expect(
                        f"{label}.{name}.{field_name} 可空性", meta["nullable"], ts_nullable
                    )
            else:
                verdict.expect(
                    f"{label}.{name}.{field_name} 可空性",
                    meta["nullable"],
                    ts_nullable,
                )
            py_kind = meta["kind"]
            if isinstance(py_kind, str) and py_kind.startswith(("ref:", "enum:")):
                verdict.expect(
                    f"{label}.{name}.{field_name} 类型（引用/枚举）",
                    py_kind,
                    ts_core,
                )
            elif isinstance(py_kind, str) and py_kind.startswith("array<"):
                py_inner = py_kind[len("array<"):-1]
                ts_inner = ts_core[len("array<"):-1] if ts_core.startswith("array<") else ts_core
                if py_inner.startswith(("ref:", "enum:")):
                    verdict.expect(
                        f"{label}.{name}.{field_name} 数组元素类型",
                        py_inner,
                        ts_inner,
                    )
                else:
                    verdict.check(
                        f"{label}.{name}.{field_name} 数组元素类型",
                        str(ts_inner).startswith(str(py_inner).split("(")[0]),
                        {"py": py_kind, "ts": ts_core},
                    )
            else:
                verdict.check(
                    f"{label}.{name}.{field_name} 类型类别",
                    str(ts_core).startswith(str(py_kind).split("(")[0]),
                    {"py": py_kind, "ts": ts_core},
                )


def main() -> int:
    verdict = B.Verdict("p26_contract_mirror")

    # ---- scores.py ↔ scores.ts
    import app.contracts.scores as scores_py
    from pydantic import BaseModel

    ts = ts_parse(
        [
            WEB_CONTRACTS / "scores.ts",
            WEB_CONTRACTS / "teaching-loop.ts",
            WEB_CONTRACTS / "assessments.ts",
            WEB_CONTRACTS / "question-bank.ts",
        ]
    )
    for entries in ts.values():
        register_aliases(entries)
    ts_scores = ts[str(WEB_CONTRACTS / "scores.ts")]
    py_scores = {
        name: obj
        for name, obj in vars(scores_py).items()
        if isinstance(obj, type)
        and issubclass(obj, BaseModel)
        and obj.__module__ == scores_py.__name__
        and not name.startswith("_")
    }
    ts_scores_interfaces = {
        name for name, entry in ts_scores.items() if entry.get("kind") == "interface"
    }
    py_only = sorted(set(py_scores) - ts_scores_interfaces)
    ts_only = sorted(ts_scores_interfaces - set(py_scores))
    # r2：ScoreImportPatchRequest 已并入 contracts/scores.ts，模型差集应为空
    verdict.expect("scores.ts 与 scores.py 的模型集合完全一致（r2）", py_only, [])
    verdict.expect("scores.ts 无多出的接口（r2）", ts_only, [])
    verdict.note(
        "r1 的镜像差项 ScoreImportPatchRequest 已并入 contracts/scores.ts（第 127-131 行），"
        "web 端 services/assessments-api.ts 只再导出、不再持有第二份形状。"
    )
    compare_models(
        verdict,
        label="scores",
        py_models=py_scores,
        ts_entries=ts_scores,
        known={
            (
                "ScoreColumnMapping",
                "itemColumns",
                "optionality",
            ): "后端 default_factory=list（可省略，按 0 个未映射叶处理）；TS 必填。"
            "方向为 TS 更严格，响应始终含该字段（非功能缺陷）。",
        },
    )
    verdict.note(f"scores 侧 Python 模型 {len(py_scores)} 个，TS 接口 {len(ts_scores_interfaces)} 个")

    # ---- r2 契约位置核对：web 端必须是"引用 + 再导出"，不得有第二份形状
    api_path = B.REPO / "apps" / "web" / "src" / "services" / "assessments-api.ts"
    api_text = api_path.read_text(encoding="utf-8")
    ts_api = ts_parse([api_path])[str(api_path)]
    verdict.check(
        "assessments-api.ts 无本地 ScoreImportPatchRequest 形状（r2）",
        "ScoreImportPatchRequest" not in set(ts_api),
        sorted(ts_api),
    )
    verdict.check(
        "assessments-api.ts 从 @/contracts/scores 再导出（r2）",
        "export type { ScoreImportPatchRequest } from '@/contracts/scores';" in api_text,
        "export type 语句",
    )
    verdict.check(
        "assessments-api.ts 从 @/contracts/scores 导入该类型（r2）",
        "ScoreImportPatchRequest," in api_text
        and "} from '@/contracts/scores';" in api_text,
        "import 块",
    )

    # ---- ScoreStatus 枚举（跨契约）
    import app.contracts.teaching_loop as tl_py

    from pydantic import TypeAdapter

    py_status = TypeAdapter(tl_py.ScoreStatus).json_schema()
    ts_status = ts[str(WEB_CONTRACTS / "teaching-loop.ts")]["ScoreStatus"]["type"]
    py_values = sorted(
        str(value)
        for branch in ([py_status] if "anyOf" not in py_status else py_status["anyOf"])
        for value in [branch.get("const"), *branch.get("enum", [])]
        if value is not None
    )
    ts_values = sorted(part.strip().strip("'") for part in ts_status.split("|"))
    verdict.expect("ScoreStatus 枚举集合", py_values, ts_values)

    # ---- 本批新增字段 1：AssessmentView.activeScoreRevisionId
    import app.contracts.assessments as assessments_py

    ts_assessments = ts[str(WEB_CONTRACTS / "assessments.ts")]
    compare_models(
        verdict,
        label="assessments",
        py_models={"AssessmentView": assessments_py.AssessmentView},
        ts_entries=ts_assessments,
        ts_scope={"AssessmentView"},
        known={
            ("AssessmentView", "classIds", "optionality"): "后端 default_factory=list，响应始终含 classIds；TS 必填（TS 更严格，非功能缺陷）。",
            ("AssessmentView", "participantCount", "optionality"): "后端默认 0，响应始终含 participantCount；TS 必填（同一类）。",
            ("AssessmentView", "state", "optionality"): "后端默认 open，响应始终含 state；TS 必填（同一类）。",
        },
    )
    py_active = py_fields(assessments_py.AssessmentView)["activeScoreRevisionId"]
    verdict.expect(
        "AssessmentView.activeScoreRevisionId 存在且可选/可空",
        {"required": py_active["required"], "nullable": py_active["nullable"]},
        {"required": False, "nullable": True},
    )
    verdict.note(f"AssessmentView.activeScoreRevisionId（py）={py_active}")

    # ---- 本批新增字段 2：QuestionKnowledgeLinkView
    import app.schemas.question_bank as qb_py

    ts_qb = ts[str(WEB_CONTRACTS / "question-bank.ts")]
    compare_models(
        verdict,
        label="question-bank",
        py_models={"QuestionKnowledgeLinkView": qb_py.QuestionKnowledgeLinkView},
        ts_entries=ts_qb,
        ts_scope={"QuestionKnowledgeLinkView"},
    )
    verdict.note(
        "QuestionKnowledgeLinkView（py）="
        + json.dumps(py_fields(qb_py.QuestionKnowledgeLinkView), ensure_ascii=False)
    )
    verdict.note(
        "QuestionKnowledgeLinkView（ts）="
        + json.dumps(ts_qb["QuestionKnowledgeLinkView"], ensure_ascii=False)
    )

    return verdict.finish(path=HERE / "p26_contract_mirror.json")


if __name__ == "__main__":
    sys.exit(main())
