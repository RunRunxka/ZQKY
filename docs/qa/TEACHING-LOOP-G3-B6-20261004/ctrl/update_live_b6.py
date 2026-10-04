"""ROOT-only refresh of CURRENT live action; historical blocks remain intact."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re

R=Path(__file__).resolve().parents[4]
O=Path(__file__).resolve().parent
target=R/'docs/CURRENT_STATUS.md'
before=O/'CURRENT-before-live-b6-r01.md'
delta=O/'CURRENT-LIVE-b6-r01-delta.json'
assert not before.exists() and not delta.exists()
raw=target.read_bytes(); before.write_bytes(raw)
at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
replacement=('## 1. 当前任务与下一动作\r\n\r\n'+at+'：G3 已独立技术关闭，历史收据与全部首败保持。限定 B6 的剩余矩阵、端点完整链 r4、15 匿名离线质量准备和四类 DOCX/实际 PDF 13 页已形成；质量与导出作者均 STOP，独立材料复核进行中。\r\n\r\n'
 '当前技术门槛为 [B6-R01](qa/TEACHING-LOOP-G3-B6-20261004/B6-R01-TASK-v1.md)：实际 UI 与修前组件反例确认，正常报告选择可取消未完成的模型/教材分类读取并留下 loading。最小 SourcePanel 修复候选正在自检；之后 ROOT 新冻结、完整 check/build、独立来源/discard 核查、新真实五字段链及原完整153。未完成这些必要门禁时不关闭限定 B6。\r\n\r\n'
 '后台/provider/DDL/恢复/导出器没有本项新改动，旧运行按逐源码绑定分列复用；当前四 PDF 为 q84e 上新实际运行，后续构建不能冒称重跑。live_run 缺明确 profile/模型/样本数/预算，teacher_review_pending，Word/WPS 排版 not_run，RAG-REL OPEN；原 B6/B7 整体未宣布完成。ROOT 管理自有隔离服务与最终文档，不提交/推送/切分支/部署，不重试旧被拒额外 HTTP 身份检查。\r\n\r\n')
pattern=rb'## 1\. \xe5\xbd\x93\xe5\x89\x8d\xe4\xbb\xbb\xe5\x8a\xa1\xe4\xb8\x8e\xe4\xb8\x8b\xe4\xb8\x80\xe5\x8a\xa8\xe4\xbd\x9c\r?\n.*?(?=### 1\.1 )'
new,n=re.subn(pattern,replacement.encode('utf-8'),raw,count=1,flags=re.S)
assert n==1
target.write_bytes(new)
sha=lambda b:hashlib.sha256(b).hexdigest()
delta.write_text(json.dumps(dict(at=at,path='docs/CURRENT_STATUS.md',beforeSHA=sha(raw),afterSHA=sha(new),
 before=before.relative_to(R).as_posix(),onlyLiveSectionUpdated=True,historicalBlocksUnchanged=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(at=at,delta=delta.relative_to(R).as_posix()),ensure_ascii=False))
