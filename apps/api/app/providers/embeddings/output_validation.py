"""Embedding 输出校验：条数、批内维度一致、有限数值、非零向量。

Ollama 与云端适配器共用同一口径（RAG-REBUILD v1.0 §4.2）：上游返回的形状或数值
只要有一处不合法就拒绝，绝不把"看似成功"的坏向量写进向量库。
"""

from __future__ import annotations

import math

from app.core.exceptions import AppError


def invalid_output(message: str) -> AppError:
    return AppError(
        f"Embedding 输出不合法：{message}",
        code="EMBEDDING_INVALID_OUTPUT",
        status_code=502,
    )


def normalize_vectors(raw: object, *, expected: int) -> list[list[float]]:
    """把上游 ``embeddings`` 归一为 ``list[list[float]]``，任何偏差都抛错。

    ``expected`` 是输入文本条数；返回条数必须相等，维度按首条对齐，
    全部数值有限且每条至少有一个非零分量。
    """
    if not isinstance(raw, list):
        raise invalid_output("响应缺少 embeddings 数组。")
    if len(raw) != expected:
        raise invalid_output(f"返回 {len(raw)} 条，与输入 {expected} 条不一致。")
    vectors: list[list[float]] = []
    dimension: int | None = None
    for index, vector in enumerate(raw):
        if not isinstance(vector, (list, tuple)) or not vector:
            raise invalid_output(f"第 {index} 条向量为空或不是数组。")
        values: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise invalid_output(f"第 {index} 条向量包含非数值元素。")
            values.append(float(value))
        if dimension is None:
            dimension = len(values)
        elif len(values) != dimension:
            raise invalid_output(
                f"第 {index} 条向量维度 {len(values)} 与首条 {dimension} 不一致。"
            )
        if not all(math.isfinite(value) for value in values):
            raise invalid_output(f"第 {index} 条向量包含非有限值。")
        if not any(value != 0.0 for value in values):
            raise invalid_output(f"第 {index} 条向量全为零向量。")
        vectors.append(values)
    return vectors


__all__ = ["invalid_output", "normalize_vectors"]
