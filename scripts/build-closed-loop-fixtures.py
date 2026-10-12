"""生成闭环测试套件（根目录 test/）：虚拟名单 xlsx / 试卷 docx / 小题分 xlsx / 教材 md。

产物与各模块导入器规则对齐（R10 用户要求）：
- 名单：学号（文本，保前导零）/姓名/性别 —— 与 roster 导入表头别名一致；
- 试卷：题号 ``N.`` 顶层 + ``(1)`` 子号，分值 ``（N 分）`` 在题号段——与试卷规则拆题一致；
  父题（含子号）不计分，子号计分；合计 100 分；
- 小题分：表头 = 学号/姓名 + 已确认试卷的计分叶题号（``11(1)`` 形式）；单元格四态
  （数值 / 空 / 缺考 / 免考）；
- 教材：markdown，章节标题 + 正文（占比远大于习题，避开习题区健全性守卫），
  含 ``## 习题1.1`` / ``## 复习参考题1.3`` 供课后习题提取。

用法：uv run --directory apps/api python ../../scripts/build-closed-loop-fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from docx import Document  # noqa: E402
from openpyxl import Workbook  # noqa: E402

OUT = REPO_ROOT / "test"

STUDENTS = [
    (f"2026{i:04d}", name, "男" if i % 2 else "女")
    for i, name in enumerate(
        [
            "张宇航", "李思远", "王雨桐", "赵一鸣", "陈晓萱", "刘子墨", "杨欣怡", "黄浩然",
            "周诗涵", "吴俊杰", "徐若曦", "孙嘉豪", "朱梦琪", "胡铭轩", "郭静宜", "何泽宇",
            "高梦洁", "林晨曦", "罗雨泽", "郑欣妍", "梁皓宇", "谢婉清", "宋佳明", "唐可欣",
            "许文博", "韩雪莹", "冯天佑", "曹梦琪", "彭子航", "董雨欣", "袁俊熙", "蒋雨晴",
            "于泽楷", "杜若涵", "叶鸿轩", "程思彤", "苏铭远", "魏雨欣", "吕承泽", "任静怡",
        ],
        start=1,
    )
]

#: 计分叶题号（与试卷一一对应）：选择题 1-6、填空 7-10、解答 11(1)/11(2)、12(1)-12(4)
SCORED = [str(i) for i in range(1, 11)] + ["11(1)", "11(2)", "12(1)", "12(2)", "12(3)", "12(4)"]
#: 各计分叶满分（与试卷标注一致）：1-10 与 11(x) 每题 5 分，12(x) 每题 10 分
CAPS = [5] * 10 + [5, 5] + [10, 10, 10, 10]

CHOICES = [
    ("下列函数中，在区间 (0, +∞) 上单调递增的是（  ）。", ["y = −x", "y = x²", "y = 1/x", "y = −x²"]),
    ("函数 f(x) = x² − 2x 的图像开口方向是（  ）。", ["向上", "向下", "向左", "向右"]),
    ("若 f(x) = 2x + 1，则 f(3) 的值为（  ）。", ["5", "6", "7", "8"]),
    ("函数 y = 1/x 在区间 (0, +∞) 上是（  ）。", ["增函数", "减函数", "先增后减", "先减后增"]),
    ("二次函数 y = x² − 4x + 3 的对称轴是（  ）。", ["x = 1", "x = 2", "x = 3", "x = 4"]),
    ("下列函数为偶函数的是（  ）。", ["f(x) = x", "f(x) = x²", "f(x) = x³", "f(x) = x + 1"]),
]

FILLS = [
    "函数 f(x) = x² − 2x 的顶点坐标是 ______ 。",
    "若函数 f(x) 在区间 (1, +∞) 上单调递增，则 f(2) ______ f(3)（填“>”或“<”）。",
    "函数 y = −x² + 4x 的最大值是 ______ 。",
    "已知 f(x) = x³，则 f ′(1) = ______ 。",
]


def build_paper() -> Path:
    doc = Document()
    doc.add_heading("函数与导数单元测试（高一年级）", level=1)
    doc.add_paragraph("考试时间：90 分钟    满分：100 分")
    doc.add_paragraph("说明：本卷共 12 题，解答应写出必要的文字说明与演算步骤。")

    doc.add_heading("一、选择题（本大题共 6 小题，每小题 5 分）", level=2)
    for index, (stem, options) in enumerate(CHOICES, start=1):
        doc.add_paragraph(f"{index}. {stem}（5分）")
        doc.add_paragraph("　　".join(f"{chr(64 + i)}. {text}" for i, text in enumerate(options, start=1)))

    doc.add_heading("二、填空题（本大题共 4 小题，每小题 5 分）", level=2)
    for index, stem in enumerate(FILLS, start=7):
        doc.add_paragraph(f"{index}. {stem}（5分）")

    doc.add_heading("三、解答题（本大题共 2 小题）", level=2)
    doc.add_paragraph("11. 已知函数 f(x) = x² − 2x + 3。")
    doc.add_paragraph("(1) 求 f(x) 的对称轴与顶点坐标；（5分）")
    doc.add_paragraph("(2) 求 f(x) 在区间 [0, 3] 上的最大值与最小值。（5分）")
    doc.add_paragraph("12. 已知函数 f(x) = x³ − 3x。")
    doc.add_paragraph("(1) 求 f(x) 的导数 f ′(x)；（10分）")
    doc.add_paragraph("(2) 求 f(x) 的单调区间；（10分）")
    doc.add_paragraph("(3) 求 f(x) 在区间 [−2, 2] 上的极值；（10分）")
    doc.add_paragraph("(4) 根据以上结论，画出 f(x) 的草图并说明其与导数符号的关系。（10分）")

    path = OUT / "试卷-函数与导数单元测试.docx"
    doc.save(path)
    return path


def build_roster() -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "名单"
    ws.append(["学号", "姓名", "性别"])
    for student_no, name, gender in STUDENTS:
        ws.append([student_no, name, gender])
    path = OUT / "名单-高一1班.xlsx"
    wb.save(path)
    return path


def build_scores() -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "小题分"
    ws.append(["学号", "姓名", "总分", *SCORED])
    for index, (student_no, name, _gender) in enumerate(STUDENTS):
        if index == 7:  # 一名学生整场缺考（总分列保持空白，缺考标记只在小题列）
            cells: list[object] = ["缺考"] * len(SCORED)
            total: object = None
        elif index == 8:  # 一名学生免考
            cells = ["免考"] * len(SCORED)
            total = None
        else:
            cells = []
            for position, cap in enumerate(CAPS):
                # 制造四态与分布：空（missing）、0 分、常规得分（上限内不越满分）
                if (index + position) % 19 == 0:
                    cells.append(None)  # missing
                elif (index + position) % 13 == 0:
                    cells.append(0)  # recorded(0)
                else:
                    cells.append((index * 3 + position * 2) % (cap + 1))
            numeric = [c for c in cells if isinstance(c, int)]
            total = sum(numeric) if numeric else None
        ws.append([student_no, name, total, *cells])
    path = OUT / "小题分-函数与导数单元测试.xlsx"
    wb.save(path)
    return path


TEXTBOOK = """# 第一章 函数与导数（测试教材·节选）

> 本文件为闭环测试用教材节选（人教A版风格改写，仅用于功能验证，不含真实教材内容）。

## 1.1 函数的概念

设 A、B 是非空实数集，如果按照某种确定的对应关系 f，使对于集合 A 中的任意一个数 x，
在集合 B 中都有唯一确定的数 y 和它对应，那么就称 f: A → B 为从集合 A 到集合 B 的一个函数，
记作 y = f(x)，x ∈ A。

其中，x 叫做自变量，x 的取值范围 A 叫做函数的定义域；与 x 的值相对应的 y 值叫做函数值，
函数值的集合 {f(x) | x ∈ A} 叫做函数的值域。

例如，一次函数 y = kx + b (k ≠ 0) 的定义域是 R，值域也是 R；二次函数 y = ax² + bx + c (a ≠ 0)
的定义域是 R，当 a > 0 时值域为 [ (4ac − b²) / (4a), +∞ )。

在定义域的不同部分有不同解析式的函数称为分段函数。例如，出租车计价、阶梯电价等实际问题
都可以用分段函数刻画。分段函数是一个函数而不是几个函数，它的定义域是各段定义域的并集，
值域是各段值域的并集。

求函数值的方法是"代入自变量、按段计算"；作函数图像的方法是"先画各段，再拼接"。
理解函数概念的关键在于：对应关系 f 必须"确定"，即给定自变量必须有唯一函数值与之对应。

## 1.2 函数的单调性

一般地，设函数 f(x) 的定义域为 I，区间 D ⊆ I。如果 ∀x₁, x₂ ∈ D，当 x₁ < x₂ 时，
都有 f(x₁) < f(x₂)，那么就称函数 f(x) 在区间 D 上单调递增；如果都有 f(x₁) > f(x₂)，
那么就称函数 f(x) 在区间 D 上单调递减。

可以证明，二次函数 y = x² − 2x 在区间 (−∞, 1] 上单调递减，在区间 [1, +∞) 上单调递增，
其图像是一条开口向上的抛物线，顶点坐标为 (1, −1)，对称轴为直线 x = 1。

判断函数单调性的常用方法有两种：一是定义法，即取值、作差、变形、定号、下结论；
二是图像法，即根据函数图像的上升或下降趋势作出判断。

用定义法证明单调性的标准步骤如下：第一步，在区间内任取 x₁ < x₂；第二步，计算
f(x₁) − f(x₂) 并因式分解；第三步，判断差的符号；第四步，得出单调性结论。
整个过程的难点在第二步，变形要彻底，直到可以判断符号为止。

复合函数的单调性遵循"同增异减"的规律：当内外层函数单调性相同时，复合函数单调递增；
单调性相反时，复合函数单调递减。这一规律在后续研究指数函数、对数函数时反复使用。

## 习题1.1

1. 判断函数 f(x) = 2x + 1 在 R 上的单调性，并用定义证明。
2. 求二次函数 f(x) = x² − 4x + 3 的单调区间与最小值。
3. 已知 f(x) 在 (0, +∞) 上单调递增，比较 f(2) 与 f(3) 的大小。

## 1.3 导数的概念

设函数 y = f(x) 在点 x₀ 的某个邻域内有定义，当自变量 x 在 x₀ 处有增量 Δx 时，
函数值相应地有增量 Δy = f(x₀ + Δx) − f(x₀)。如果当 Δx → 0 时，Δy/Δx 的极限存在，
则称函数 f(x) 在点 x₀ 处可导，并称这个极限为 f(x) 在点 x₀ 处的导数，记作 f ′(x₀)。

导数的几何意义是曲线 y = f(x) 在点 (x₀, f(x₀)) 处切线的斜率。据此可以研究函数的
单调性：如果在区间 D 上 f ′(x) > 0，那么 f(x) 在 D 上单调递增；如果 f ′(x) < 0，
那么 f(x) 在 D 上单调递减。

例如，f(x) = x³ − 3x 的导数为 f ′(x) = 3x² − 3，令 f ′(x) = 0 得 x = ±1；
在 (−∞, −1) 与 (1, +∞) 上 f ′(x) > 0，函数单调递增；在 (−1, 1) 上 f ′(x) < 0，函数单调递减。

常用导数公式：常函数的导数为零；幂函数 xⁿ 的导数为 nxⁿ⁻¹；正弦函数的导数为余弦函数；
余弦函数的导数为负的正弦函数。导数的运算法则包括加法法则、乘法法则与除法法则，
它们是后续求函数极值、最值的基础工具。

利用导数研究函数的一般流程是：先求定义域，再求导函数，令导函数为零求出驻点，
列表讨论导函数在各区间上的符号，最后结合端点值与驻点值写出单调区间与极值。

## 复习参考题1.3

1. 求函数 f(x) = x³ − 3x 的导数，并求其在 x = 2 处的导数值。
2. 研究函数 f(x) = x² − 2x + 3 的单调性与极值，并画出草图。
"""


def build_textbook() -> Path:
    path = OUT / "教材-函数与导数节选.md"
    path.write_text(TEXTBOOK, encoding="utf-8")
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [build_paper(), build_roster(), build_scores(), build_textbook()]
    manifest = {
        "generatedBy": "scripts/build-closed-loop-fixtures.py",
        "students": len(STUDENTS),
        "scoredLeaves": SCORED,
        "files": [p.name for p in paths],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for path in paths:
        print(f"OK {path.name} ({path.stat().st_size} bytes)")
    print("manifest.json 已写入；学生数 =", len(STUDENTS), "；计分叶 =", len(SCORED))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
