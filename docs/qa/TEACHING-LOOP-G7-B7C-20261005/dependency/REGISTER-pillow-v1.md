# CTRL 登记：原生页图严格解码依赖（Pillow）v1

2026-10-05。对应 R-B7B-NATIVE-01/P2 的最小修复：`trial_result_check.py` 的 `native_return` 不再只看文件头，而用真实图像解码器核允许格式、与扩展名匹配、正尺寸与完整像素解码。

## 依据与选择

- 用户指令：“复用可用且可交付的真实解码器，不手写一套 JPEG/WebP 解析器。若需引入图像依赖，由 CTRL 唯一登记后端 pyproject/uv 锁及固定版本，先确认运行环境和必要自检；不顺带升级框架/其他包。”
- 仓库现有依赖（numpy/pypdf/python-docx/openpyxl/math2docx/jieba 等）与 Python 标准库均不提供 PNG/JPEG/WebP 像素解码；手写解析器被明确禁止。
- 选择 **Pillow**（成熟、可交付、官方 wheel 自带 zlib/jpg/webp 支持），仅新增一个包、无传递依赖。

## 登记内容

- `apps/api/pyproject.toml`：新增 `"pillow==12.3.0"`（固定版本）。
- `apps/api/uv.lock`：`uv lock` 后仅新增 Pillow 12.3.0 相关条目（新增 73 行，0 行修改/删除；未顺带升级任何既有包）。
- 安装目标：`apps/api/.venv`（`uv sync`），与 `scripts/teaching-quality` 工具的实际运行解释器一致。
- 运行环境自检（`tools/dependency_selfcheck.py` → `dependency/DEPENDENCY-SELFCHECK-v1.json`）：Pillow 12.3.0；`zlib/jpg/webp` 特性均为 True；`ImageFile.LOAD_TRUNCATED_IMAGES=False`（严格模式）。
- 声明资源上界：≤32MiB/文件、≤40,000,000 像素、单边 ≤20,000、帧数 ≤64。

## 自检结果（作者自检，非独立验收）

`dependency/DEPENDENCY-SELFCHECK-v1.json`：合法 PNG/JPEG(.jpg)/JPEG(.jpeg)/WebP 全部接受；审查者三反例（8 字节 PNG 头、3 字节 JPEG 头、12 字节 RIFF+WEBP 头）与零字节、截断、坏 CRC、格式/扩展名错配、PDF 伪装、超资源全部拒绝，且 `field=page.evidence`。

另记：原 `test_trial_result_v1.py` 的 1 像素 PNG 常量实际带坏 IDAT 校验（严格解码正确拒绝），作者对照已改为运行时可解码的合成 1 像素 PNG；它只作工具正常对照，不构成真实页核，顶层 native 仍 pending。

## 边界

解码校验只证明“该文件是被允许格式的完整可解码图像”，**不**证明 Word/WPS 实际打开、页面内容真实性或排版合格；人工返回与 native 顶层仍 pending，`createsNativeApproval=false` 保持。依赖或解码错误显式拒绝，不静默略过。
