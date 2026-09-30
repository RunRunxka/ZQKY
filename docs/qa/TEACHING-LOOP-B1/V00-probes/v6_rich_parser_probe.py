"""V6 富内容解析探针（TEACHING-LOOP B1 / V00）。

自建 DOCX（含 vMerge 纵向合并 + gridSpan 横向合并 + 表头行 + 图片 + 行内/独立 OMML +
未知对象 + 空段落 + body 级未知元素），验证：
块顺序与定位；表格合并单元格（rowSpan/colSpan、被覆盖单元格不重复、续接文本不丢）；
图片真实字节（sha256 与 assets 一致、可读回、尺寸像素）；OMML 与原件 XML 逐字节一致；
未知对象进 issues 且带定位；共同材料分组正确且确定。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_common import Probe, ensure_api_on_path, temp_data_root  # noqa: E402

p = Probe("v6_rich_parser")
root = temp_data_root("v6")
ensure_api_on_path()

import _rich_fixture as fx  # noqa: E402

from app.contracts.teaching_loop import RichOrigin  # noqa: E402
from app.services.assets.store import AssetStore  # noqa: E402
from app.services.rich_content import (  # noqa: E402
    group_shared_materials,
    parse_docx_rich,
    rich_content_from_blocks,
)

docx_path = root / "sample.docx"
spec = fx.build_sample(docx_path)
assets = AssetStore(root / "assets")
parsed = parse_docx_rich(
    path=docx_path,
    file_name="sample.docx",
    assets=assets,
    origin=RichOrigin(
        original_asset_id="orig-1",
        original_sha256=hashlib.sha256(docx_path.read_bytes()).hexdigest(),
        source_locator={"page": 1},
    ),
)

kinds = {block.id: block.kind for block in parsed.blocks}
p.check(
    "v6.1a 块顺序与 id 符合原件（p1..p3、t4、p5、p5-1、p6、p7、p7-1、p8、p9）",
    [block.id for block in parsed.blocks]
    == ["p1", "p2", "p3", "t4", "p5", "p5-1", "p6", "p7", "p7-1", "p8", "p9"],
    json.dumps({block.id: block.kind for block in parsed.blocks}, ensure_ascii=False),
)
p.check(
    "v6.1b 块类型判别正确（段落/表格/公式/图片）",
    kinds
    == {
        "p1": "paragraph",
        "p2": "paragraph",
        "p3": "paragraph",
        "t4": "table",
        "p5": "paragraph",
        "p5-1": "formula",
        "p6": "formula",
        "p7": "paragraph",
        "p7-1": "image",
        "p8": "paragraph",
        "p9": "paragraph",
    },
    json.dumps(kinds, ensure_ascii=False),
)
p.check(
    "v6.1c 空段落不产生块（块数=11，body 级 sdt 不占块序号）",
    len(parsed.blocks) == 11,
    f"blocks={len(parsed.blocks)}",
)
locators_ok = all(
    isinstance(parsed.locators.get(block.id, {}).get("blockStart"), int)
    and parsed.locators[block.id]["blockStart"] >= 1
    for block in parsed.blocks
)
p.check(
    "v6.1d 每个块都有 1 基来源定位（blockStart/blockEnd）",
    locators_ok
    and parsed.locators["p1"]["blockStart"] == 1
    and parsed.locators["t4"]["blockStart"] == 4
    and parsed.locators["p9"]["blockStart"] == 9,
    json.dumps({key: parsed.locators[key] for key in ("p1", "t4", "p9")}, ensure_ascii=False),
)

# ------------------------------------------------------------------ 表格
table = next(block for block in parsed.blocks if block.kind == "table")
cells = [(cell.text, cell.is_header, cell.row_span, cell.col_span) for cell in table.cells]
p.check(
    "v6.2a columnCount 一律填写且等于网格宽度（3）",
    table.column_count == 3,
    f"columnCount={table.column_count}",
)
p.check(
    "v6.2b 合并单元格只在起始位置出现一次（7 个单元格，rowSpan/colSpan 正确）",
    cells == spec["table_cells"],
    json.dumps(cells, ensure_ascii=False),
)
p.check(
    "v6.2c 被覆盖的续接单元格不产生重复条目（3 行合计 7 项而非 9 项）",
    len(table.cells) == 7,
    f"cells={len(table.cells)}",
)
p.check(
    "v6.2d 续接单元格可见文本并入起始单元格（不丢字）",
    cells[2][0] == "纵向起始\n纵向续接文本" and cells[2][2] == 2,
    repr(cells[2][0]),
)
p.check(
    "v6.2e 表头行标记（首行 + tblHeader → isHeader）",
    cells[0][1] is True and cells[1][1] is True and cells[2][1] is False,
    json.dumps([item[1] for item in cells]),
)
p.check(
    "v6.2f 表格定位附 tableColumns/tableRows（与 columnCount 同值）",
    parsed.locators["t4"].get("tableColumns") == 3 and parsed.locators["t4"].get("tableRows") == 3,
    json.dumps(parsed.locators["t4"], ensure_ascii=False),
)

# ------------------------------------------------------------------ 图片
image = next(block for block in parsed.blocks if block.kind == "image")
p.check(
    "v6.3a 图片块 assetId=受管 blob_key 且尺寸像素=wp:extent 换算（96px）",
    image.asset_id.startswith("blobs/") and image.width == 96 and image.height == 96,
    json.dumps({"assetId": image.asset_id[:20] + "…", "width": image.width, "height": image.height}),
)
p.check(
    "v6.3b assets[].sha256 == 图片字节 sha256（真实字节）",
    len(parsed.assets) == 1
    and parsed.assets[0].sha256 == spec["image_sha256"]
    and parsed.assets[0].media_type == "image/png",
    json.dumps(
        {"assets": [{"sha256": item.sha256[:12] + "…", "media": item.media_type} for item in parsed.assets],
         "expected": spec["image_sha256"][:12] + "…"},
        ensure_ascii=False,
    ),
)
read_back = assets.read(image.asset_id)
p.check(
    "v6.3c 图片可读回且与源字节一致",
    read_back == spec["image_bytes"],
    f"bytes={len(read_back)} match={read_back == spec['image_bytes']}",
)

# ------------------------------------------------------------------ OMML
formula_blocks = [block for block in parsed.blocks if block.kind == "formula"]
source_serials = fx.source_omml_serials(docx_path)
p.check(
    "v6.4a 公式块数量与文档顺序一致（行内 + 独立 = 2）",
    len(formula_blocks) == 2 and [block.id for block in formula_blocks] == ["p5-1", "p6"],
    json.dumps([block.id for block in formula_blocks]),
)
p.check(
    "v6.4b ommlXml 与原件 word/document.xml 的 m:oMath 逐字节一致（不改写）",
    [block.omml_xml for block in formula_blocks] == source_serials,
    json.dumps(
        {"parsed": [block.omml_xml for block in formula_blocks], "source": source_serials},
        ensure_ascii=False,
    )[:600],
)
p.check(
    "v6.4c 行内公式段落仍保留题干文本块",
    any(
        block.kind == "paragraph" and block.text == "1. 题干文字"
        for block in parsed.blocks
    ),
    json.dumps([getattr(block, "text", "") for block in parsed.blocks if block.kind == "paragraph"], ensure_ascii=False)[:200],
)

# ------------------------------------------------------------------ issues / warnings
issue_codes = [(issue.code, issue.block_id, sorted(issue.source_locator)) for issue in parsed.issues]
p.check(
    "v6.5a 未知对象（w:object）进 issues 且带块定位",
    any(
        issue.code == "UNSUPPORTED_OBJECT" and issue.block_id == "p8" and "blockStart" in issue.source_locator
        for issue in parsed.issues
    ),
    json.dumps(issue_codes, ensure_ascii=False)[:400],
)
p.check(
    "v6.5b body 级未知元素（w:sdt）进 issues 且带 bodyIndex",
    any(
        issue.code == "UNSUPPORTED_OBJECT" and "bodyIndex" in issue.source_locator
        for issue in parsed.issues
    ),
    json.dumps(issue_codes, ensure_ascii=False)[:400],
)
p.check(
    "v6.5c 原件散列一致时不产生来源告警",
    parsed.warnings == (),
    json.dumps(parsed.warnings, ensure_ascii=False),
)
mismatch_parsed = None
try:
    mismatch_parsed = parse_docx_rich(
        path=docx_path,
        file_name="sample.docx",
        assets=assets,
        origin=RichOrigin(
            original_asset_id="orig-2", original_sha256="0" * 64, source_locator={}
        ),
    )
except Exception as exc:  # noqa: BLE001
    p.check("v6.5d 散列不符只警告不拒绝", False, f"{type(exc).__name__}: {exc}")
else:
    p.check(
        "v6.5d 散列不符只警告不拒绝（内容权威）",
        len(mismatch_parsed.warnings) == 1 and "原件散列" in mismatch_parsed.warnings[0],
        json.dumps(mismatch_parsed.warnings, ensure_ascii=False)[:200],
    )

# ------------------------------------------------------------------ 共同材料分组
materials, unassigned = group_shared_materials(parsed.blocks, parsed.locators)
p.check(
    "v6.6a 首个题号段之前的块归入共同材料组（material-1 = p1/p2/p3/t4）",
    len(materials) == 1
    and materials[0].id == "material-1"
    and [block.id for block in materials[0].blocks] == ["p1", "p2", "p3", "t4"],
    json.dumps([[block.id for block in material.blocks] for material in materials], ensure_ascii=False),
)
p.check(
    "v6.6b 题号段本身不进材料组（留在 unassigned）",
    "p5" in unassigned and "p9" in unassigned,
    json.dumps(list(unassigned)),
)
p.check(
    "v6.6c 材料组后的零散块不猜（p6/p7/p7-1/p8 都在 unassigned）",
    set(unassigned) == {"p5", "p5-1", "p6", "p7", "p7-1", "p8", "p9"},
    json.dumps(list(unassigned)),
)
p.check(
    "v6.6d 分组确定（同输入重复调用结果一致）",
    [[block.id for block in material.blocks] for material in group_shared_materials(parsed.blocks, parsed.locators)[0]]
    == [[block.id for block in material.blocks] for material in materials],
    "deterministic",
)

assembled = rich_content_from_blocks(
    blocks=parsed.blocks,
    materials=materials,
    assets=parsed.assets,
    origin=RichOrigin(
        original_asset_id="orig-1",
        original_sha256=hashlib.sha256(docx_path.read_bytes()).hexdigest(),
        source_locator={"page": 1},
    ),
)
material_table = next(
    block for material in assembled.shared_materials for block in material.blocks if block.kind == "table"
)
p.check(
    "v6.6e 组装 RichContentV2：题干=非材料块；材料里的表格 columnCount 原样保留",
    [block.id for block in assembled.stem_blocks] == ["p5", "p5-1", "p6", "p7", "p7-1", "p8", "p9"]
    and material_table.column_count == 3
    and material_table.cells[2].row_span == 2
    and assembled.shared_materials[0].blocks[3] is table,
    json.dumps(
        {
            "stem": [block.id for block in assembled.stem_blocks],
            "materialTable": {"id": material_table.id, "columnCount": material_table.column_count},
        },
        ensure_ascii=False,
    ),
)
stem_conflict = None
try:
    rich_content_from_blocks(
        blocks=parsed.blocks,
        materials=materials,
        assets=parsed.assets,
        origin=RichOrigin(original_asset_id="o", original_sha256="0" * 64, source_locator={}),
        stem_block_ids=["p1"],
    )
except Exception as exc:  # noqa: BLE001
    stem_conflict = exc
p.check(
    "v6.6f 同一块既作题干又作材料 → 明确拒绝（不静默丢弃）",
    stem_conflict is not None and getattr(stem_conflict, "status_code", None) == 422,
    f"{type(stem_conflict).__name__}: {getattr(stem_conflict, 'code', None)} {stem_conflict}",
)

sys.exit(p.finish())
