"""生成闭环测试套件（根目录 test/）：虚拟名单 xlsx / 试卷 docx / 小题分 xlsx / 教材 md。

产物与各模块导入器规则对齐（R10 用户要求）：
- 名单：学号（文本，保前导零）/姓名/性别 —— 与 roster 导入表头别名一致；
- 试卷：题号 ``N.`` 顶层 + ``(1)`` 子号，分值 ``（N 分）`` 在题号段——与试卷规则拆题一致；
  父题（含子号）不计分，子号计分；合计 100 分；
- 小题分：表头 = 学号/姓名 + 已确认试卷的计分叶题号（``11(1)`` 形式）；单元格四态
  （数值 / 空 / 缺考 / 免考）；
- 教材：markdown，**6 节 = 6 个知识点**（1.1 函数的概念与表示 / 1.2 函数的单调性 /
  1.3 函数的奇偶性 / 1.4 二次函数的图像与性质 / 1.5 导数的概念与运算 /
  1.6 利用导数研究函数的单调性与极值），每节正文即该知识点的教材依据（占比远大于习题，
  避开习题区健全性守卫），每节末尾 ``### 习题1.x`` + 章末 ``## 复习参考题1`` 供课后习题提取；
  正文内容与 ``test/试卷-函数与导数单元测试.docx`` 的知识点一一对应（演示闭环：教材目录成树 →
  题库提取/补题 → 试卷知识点 → 学情 → 教案/练习）。

用法（可只重建单个目标，避免重写其余文件的字节）：
    uv run --directory apps/api python ../../scripts/build-closed-loop-fixtures.py            # 全部
    uv run --directory apps/api python ../../scripts/build-closed-loop-fixtures.py textbook   # 只重建教材
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


TEXTBOOK = """# 第一章 函数与导数

> 本文件为闭环演示用教材节选（人教A版风格改写，仅用于功能验证，不含真实教材内容）。
> 若把本文导入教材资料库后执行「从教材目录生成树」，应得到 1 章 6 节共 7 个知识点节点：
> 第一章 函数与导数 / 1.1 函数的概念与表示 / 1.2 函数的单调性 / 1.3 函数的奇偶性 /
> 1.4 二次函数的图像与性质 / 1.5 导数的概念与运算 / 1.6 利用导数研究函数的单调性与极值。
> 每节正文即为该知识点的教材依据；每节末尾的「习题」是「从教材课后习题提取」的来源。

## 1.1 函数的概念与表示

设 A、B 是非空实数集，如果按照某种确定的对应关系 f，使对于集合 A 中的任意一个数 x，
在集合 B 中都有唯一确定的数 y 和它对应，那么就称 f: A → B 为从集合 A 到集合 B 的一个函数，
记作 y = f(x)，x ∈ A。

其中，x 叫做自变量，x 的取值范围 A 叫做函数的定义域；与 x 的值相对应的 y 值叫做函数值，
函数值的集合 {f(x) | x ∈ A} 叫做函数的值域。定义域与对应关系一旦确定，函数就随之确定，
所以两个函数相同，必须定义域相同、对应关系也相同。

求函数值的基本方法是"代入自变量、按对应关系计算"。例如对于 f(x) = 2x + 1，
把 x = 3 代入得 f(3) = 2 × 3 + 1 = 7；对于 g(x) = x² − 2x，有 g(0) = 0、g(−1) = 3。
一次函数 y = kx + b (k ≠ 0) 的定义域是 R，值域也是 R；反比例函数 y = k/x (k ≠ 0)
的定义域是 {x | x ≠ 0}，值域是 {y | y ≠ 0}；二次函数 y = ax² + bx + c (a ≠ 0) 的定义域是 R。

求定义域要注意三件事：分式的分母不能为零；偶次根式的被开方数必须非负；
实际问题还要受实际意义的限制。例如 y = 1/x 的定义域是 {x | x ≠ 0}，
y = √(x − 1) 的定义域是 {x | x ≥ 1}，y = x² + 1 在实数范围内的定义域是 R。

在定义域的不同部分有不同解析式的函数称为分段函数。例如出租车计价、阶梯电价等实际问题
都可以用分段函数刻画。分段函数是一个函数而不是几个函数，它的定义域是各段定义域的并集，
值域是各段值域的并集；求分段函数的函数值时，要先判断自变量落在哪一段，再代入该段的解析式。

函数的表示方法有三种：解析法（用解析式表示对应关系，简明便于计算）、图像法（用图像直观
反映变化趋势）与列表法（用表格列出部分对应值，适合数据类问题）。三种方法各有优劣，
实际研究中常常配合使用，例如先用解析式求值，再画图像观察整体特征。

## 1.2 函数的单调性

一般地，设函数 f(x) 的定义域为 I，区间 D ⊆ I。如果 ∀x₁, x₂ ∈ D，当 x₁ < x₂ 时，
都有 f(x₁) < f(x₂)，那么就称函数 f(x) 在区间 D 上单调递增；如果都有 f(x₁) > f(x₂)，
那么就称函数 f(x) 在区间 D 上单调递减。单调递增或单调递减统称为单调性，
区间 D 叫做函数的单调区间。

可以证明，二次函数 y = x² − 2x 在区间 (−∞, 1] 上单调递减，在区间 [1, +∞) 上单调递增，
其图像是一条开口向上的抛物线，顶点坐标为 (1, −1)，对称轴为直线 x = 1。
一次函数 y = kx + b 当 k > 0 时在 R 上单调递增，当 k < 0 时在 R 上单调递减；
反比例函数 y = 1/x 在 (0, +∞) 与 (−∞, 0) 上均单调递减。

判断函数单调性的常用方法有两种：一是定义法，即取值、作差、变形、定号、下结论；
二是图像法，即根据函数图像的上升或下降趋势作出判断。

用定义法证明单调性的标准步骤如下：第一步，在指定区间内任取 x₁ < x₂；
第二步，计算 f(x₁) − f(x₂) 并因式分解或通分；第三步，判断差的符号；
第四步，得出单调性结论。整个过程的难点在第二步，变形要彻底，直到可以判断符号为止。

复合函数的单调性遵循"同增异减"的规律：当内外层函数的单调性相同时，复合函数单调递增；
单调性相反时，复合函数单调递减。这一规律在后续研究指数函数、对数函数时反复使用。

## 1.3 函数的奇偶性

一般地，设函数 f(x) 的定义域为 I。如果 ∀x ∈ I，都有 −x ∈ I，且 f(−x) = f(x)，
那么就称函数 f(x) 为偶函数；如果 ∀x ∈ I，都有 −x ∈ I，且 f(−x) = −f(x)，
那么就称函数 f(x) 为奇函数。定义域关于原点对称是讨论奇偶性的前提：
如果定义域本身不关于原点对称，函数既不是奇函数也不是偶函数。

偶函数的图像关于 y 轴对称，奇函数的图像关于原点对称。这一图像特征既可以帮助判断奇偶性，
也可以利用奇偶性简化作图：只要画出 y 轴一侧的图像，就可以对称地得到另一侧。

判断函数奇偶性的步骤是：第一步，求出定义域并检查它是否关于原点对称；
第二步，计算 f(−x) 并与 f(x)、−f(x) 比较；第三步，按定义给出结论。
例如 f(x) = x² 满足 f(−x) = (−x)² = x² = f(x)，是偶函数；f(x) = x³ 满足
f(−x) = (−x)³ = −x³ = −f(x)，是奇函数；f(x) = 1/x 也是奇函数；
而 f(x) = x + 1 既不是奇函数也不是偶函数，因为 f(−1) = 0、f(1) = 2，
既不等于 f(1)，也不等于 −f(1)。

奇偶性与单调性一样，是研究函数性质的重要工具：奇函数在关于原点对称的两个区间上
单调性相同，偶函数在关于原点对称的两个区间上单调性相反。

## 1.4 二次函数的图像与性质

一般地，把形如 y = ax² + bx + c (a ≠ 0) 的函数叫做二次函数。通过配方可以把它写成
顶点式 y = a(x − h)² + k，其中 h = −b/(2a)，k = (4ac − b²)/(4a)；
顶点坐标为 (−b/(2a), (4ac − b²)/(4a))，对称轴为直线 x = −b/(2a)。

二次函数的图像是抛物线：当 a > 0 时开口向上，函数有最小值 k，值域为 [k, +∞)；
当 a < 0 时开口向下，函数有最大值 k，值域为 (−∞, k]。开口向上的抛物线在对称轴
左侧单调递减、右侧单调递增；开口向下的抛物线在对称轴左侧单调递增、右侧单调递减。

例如 y = x² − 4x + 3 配方得 y = (x − 2)² − 1，所以对称轴为直线 x = 2，
顶点坐标为 (2, −1)，当 x = 2 时取得最小值 −1，单调递减区间为 (−∞, 2]，
单调递增区间为 [2, +∞)。又如 y = −x² + 4x 配方得 y = −(x − 2)² + 4，
开口向下，当 x = 2 时取得最大值 4。

求二次函数在闭区间 [m, n] 上的最值要按对称轴与区间的位置关系分类讨论：
若对称轴在区间内，最小值（或最大值）在顶点处取得，另一个最值在离对称轴较远的端点取得；
若对称轴在区间左侧或右侧，函数在区间上单调，两个最值都在端点处取得。
例如求 f(x) = x² − 2x + 3 在 [0, 3] 上的最值：对称轴 x = 1 落在区间内，
最小值 f(1) = 2；最大值在端点取得，比较 f(0) = 3 与 f(3) = 6，得最大值 6。

## 1.5 导数的概念与运算

设函数 y = f(x) 在点 x₀ 的某个邻域内有定义，当自变量 x 在 x₀ 处有增量 Δx 时，
函数值相应地有增量 Δy = f(x₀ + Δx) − f(x₀)。比值 Δy/Δx 叫做函数从 x₀ 到 x₀ + Δx
的平均变化率；如果当 Δx → 0 时，Δy/Δx 的极限存在，则称函数 f(x) 在点 x₀ 处可导，
并称这个极限为 f(x) 在点 x₀ 处的导数，记作 f ′(x₀)。

导数的几何意义是曲线 y = f(x) 在点 (x₀, f(x₀)) 处切线的斜率，即
f ′(x₀) = k_切线。平均变化率刻画的是平均变化快慢，导数刻画的是瞬时变化快慢，
这是导数区别于平均变化率的本质所在。

常用导数公式：常函数的导数为零，即 C′ = 0；幂函数 xⁿ 的导数为 nxⁿ⁻¹，
例如 (x²)′ = 2x、(x³)′ = 3x²；正弦函数的导数为余弦函数，(sin x)′ = cos x；
余弦函数的导数为负的正弦函数，(cos x)′ = −sin x。

导数的运算法则包括：加法法则 (f(x) ± g(x))′ = f ′(x) ± g′(x)；
乘法法则 (f(x)g(x))′ = f ′(x)g(x) + f(x)g′(x)；
除法法则 (f(x)/g(x))′ = [f ′(x)g(x) − f(x)g′(x)] / g²(x)（g(x) ≠ 0）。
它们是后续求函数极值、最值的基础工具。例如 f(x) = x³ 的导数为 f ′(x) = 3x²，
所以 f ′(1) = 3；g(x) = x³ − 3x 的导数为 g′(x) = 3x² − 3。

## 1.6 利用导数研究函数的单调性与极值

在区间 D 上，如果 f ′(x) > 0，那么 f(x) 在 D 上单调递增；如果 f ′(x) < 0，
那么 f(x) 在 D 上单调递减。因此导数的符号直接决定函数的升降：
导数为正对应图像上升，导数为负对应图像下降，导数等于零的位置是升降变化的分界。

利用导数研究函数的一般流程是：先求定义域，再求导函数，令导函数为零求出驻点，
列表讨论导函数在各区间上的符号，最后写出单调区间与极值。

一般地，设函数 f(x) 在点 x₀ 附近有定义，如果对 x₀ 附近的任意 x（x ≠ x₀），
都有 f(x) < f(x₀)，就称 f(x₀) 是函数 f(x) 的极大值，x₀ 叫做极大值点；
如果都有 f(x) > f(x₀)，就称 f(x₀) 是极小值，x₀ 叫做极小值点。
极大值与极小值统称极值。极值点出现在导数为零或导数不存在的点处，
但导数为零的点不一定是极值点，还要看导数在该点两侧是否变号。

例如 f(x) = x³ − 3x 的导数为 f ′(x) = 3x² − 3，令 f ′(x) = 0 得 x = ±1；
在 (−∞, −1) 与 (1, +∞) 上 f ′(x) > 0，函数单调递增；在 (−1, 1) 上 f ′(x) < 0，
函数单调递减。所以 x = −1 是极大值点，极大值 f(−1) = 2；x = 1 是极小值点，
极小值 f(1) = −2。

求函数在闭区间 [a, b] 上的最值时，只需求出区间内的所有极值，再与端点值
f(a)、f(b) 比较，其中最大的就是最大值，最小的就是最小值。例如 f(x) = x³ − 3x
在 [−2, 2] 上的极值为 2 与 −2，端点为 f(−2) = −2、f(2) = 2，
所以最大值是 2，最小值是 −2。

## 习题1.1

1. 已知 f(x) = 2x + 1，求 f(3) 的值。
2. 求函数 y = 1/x 的定义域与值域；求函数 y = √(x − 1) 的定义域。
3. 已知分段函数 f(x) = x + 1 (x < 0)，f(x) = x² (x ≥ 0)，求 f(−2) 与 f(2) 的值。

## 习题1.2

1. 判断函数 f(x) = 2x + 1 在 R 上的单调性，并用定义证明。
2. 求二次函数 f(x) = x² − 4x + 3 的单调区间与最小值。
3. 已知 f(x) 在 (0, +∞) 上单调递增，比较 f(2) 与 f(3) 的大小。
4. 下列函数中，在区间 (0, +∞) 上单调递减的是（  ）。
A. y = 2x + 1
B. y = x²
C. y = 1/x
D. y = x³

## 习题1.3

1. 判断函数 f(x) = x² 的奇偶性，并用定义说明理由。
2. 判断函数 f(x) = x³ 的奇偶性；判断 f(x) = 1/x 的奇偶性。
3. 判断函数 f(x) = x + 1 是否具有奇偶性，并说明理由。
4. 已知 f(x) 是偶函数且 f(2) = 3，求 f(−2) 的值。

## 习题1.4

1. 求二次函数 y = x² − 4x + 3 的对称轴与顶点坐标。
2. 求二次函数 y = −x² + 4x 的最大值，并说明取得最大值时 x 的取值。
3. 求二次函数 f(x) = x² − 2x + 3 在区间 [0, 3] 上的最大值与最小值。
4. 已知 f(x) = x² − 2x + 3，求 f(x) 的单调区间。

## 习题1.5

1. 求函数 f(x) = x³ 的导数 f ′(x)，并求 f ′(1) 的值。
2. 求函数 f(x) = x³ − 3x 的导数，并求其在 x = 2 处的导数值。
3. 求函数 y = x² − 2x 的导数。
4. 用导数的几何意义说明：曲线 y = x² 在点 (1, 1) 处切线的斜率为 2。

## 习题1.6

1. 求函数 f(x) = x³ − 3x 的单调区间。
2. 求函数 f(x) = x³ − 3x 的极值。
3. 求函数 f(x) = x³ − 3x 在区间 [−2, 2] 上的最大值与最小值。
4. 结合导数的符号说明函数图像上升、下降与极值点的关系。

## 复习参考题1

1. 已知 f(x) = x² − 2x + 3，求 f(x) 的对称轴、顶点坐标、单调区间与最小值，
并求 f(x) 在区间 [0, 3] 上的最大值与最小值。
2. 判断 f(x) = x³ 的奇偶性与单调性，并说明理由。
3. 利用导数研究 f(x) = x³ − 3x 的单调区间与极值，并画出函数草图。
"""


def build_textbook() -> Path:
    path = OUT / "教材-函数与导数节选.md"
    path.write_text(TEXTBOOK, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    """重建套件文件；可只重建指定目标（``textbook`` / ``paper`` / ``roster`` / ``scores``）。

    不带参数重建全部四件套；单个目标名避免为改一份 markdown 而重写 docx/xlsx 的字节。
    manifest 始终登记完整四件套（内容与顺序固定）。
    """
    builders = [
        ("paper", "试卷-函数与导数单元测试.docx", build_paper),
        ("roster", "名单-高一1班.xlsx", build_roster),
        ("scores", "小题分-函数与导数单元测试.xlsx", build_scores),
        ("textbook", "教材-函数与导数节选.md", build_textbook),
    ]
    wanted = {item.strip() for item in (argv or []) if item.strip()}
    unknown = wanted - {name for name, _file, _builder in builders}
    if unknown:
        print(f"未知目标：{'、'.join(sorted(unknown))}；可选：{'、'.join(name for name, _f, _b in builders)}")
        return 2
    selected = [(name, builder) for name, _file, builder in builders if not wanted or name in wanted]
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [builder() for _name, builder in selected]
    manifest = {
        "generatedBy": "scripts/build-closed-loop-fixtures.py",
        "students": len(STUDENTS),
        "scoredLeaves": SCORED,
        "files": [file for _name, file, _builder in builders],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for path in paths:
        print(f"OK {path.name} ({path.stat().st_size} bytes)")
    print("manifest.json 已写入；学生数 =", len(STUDENTS), "；计分叶 =", len(SCORED))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
