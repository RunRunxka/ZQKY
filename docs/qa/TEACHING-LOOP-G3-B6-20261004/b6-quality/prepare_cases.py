"""Handwritten anonymous fixture inputs and literal teacher-rule expectations.

No app/aggregate/provider is imported. Expected numbers are hand enumerated,
not computed from production aggregation or generated candidate text.
"""
from pathlib import Path
import copy
import json

OUT = Path(__file__).resolve().parent
LOSS = dict(selectedCount=1, validCount=1, needsCount=1, incompleteCount=0,
            noEvidenceCount=0, fullCreditCount=0, numerator=1, denominator=1, ratio=1.0)
FULL = dict(selectedCount=1, validCount=1, needsCount=0, incompleteCount=0,
            noEvidenceCount=0, fullCreditCount=1, numerator=0, denominator=1, ratio=0.0)
GAPS = dict(selectedCount=1, validCount=0, needsCount=0, incompleteCount=1,
            noEvidenceCount=1, fullCreditCount=0, numerator=0, denominator=0, ratio=None)

def case(key, title, rationale, **kw):
    value = dict(caseId=key, title=title, oracleOrigin="Independent QA handwriting from authorized any_loss_v1 teacher rules; pending human teacher confirmation",
        rationale=rationale, durationMinutes=40, stageMinutes=[10,10,10,10],
        items=[dict(maxScoreUnits=100, knowledgeIndexes=[0])],
        participants=[dict(alias="a", classIndex=0, attemptNo=1, attendance="present", cells=[["recorded",50]])],
        selectedParticipantIndexes=[0], selectedClassIndex=0, selectedKnowledgeIndexes=[0],
        expectedTargetCounts=[copy.deepcopy(LOSS)], selectedFields=["teachingDesign","process"],
        materialCase="positive", requestedClaimSupported=True, questionSource="confirmed",
        requirements="依据固定有理数加法片段与匿名班级计数复习。具体错因须用课堂检测核实；不得臆造学生原因。",
        interpretation="有已记录失分，需巩固只是本次关联提示，不能推断长期能力或具体错因。",
        forbiddenClaims=["人数互斥相加", "长期掌握概率", "从综合题失分推断具体错误步骤", "自动发布未审核题"],
        humanReviewStatus="teacher_review_pending", liveStatus="live_run待输入")
    value.update(kw)
    return value

cases = [
    case("C01","单知识点失分","仅一名被选学生、一项recorded50/100，所以有效1、需巩固1，分母为1。"),
    case("C02","有效零分","recorded0是真实有效成绩，不能当missing或absent；有效1、需巩固1。",
        participants=[dict(alias="a",classIndex=0,attemptNo=1,attendance="present",cells=[["recorded",0]])]),
    case("C03","失分与缺失并存","同一学生两叶关联单KP：50/100及missing。需巩固和信息不全均为1，两者重叠，不能相加为两人。",
        items=[dict(maxScoreUnits=100,knowledgeIndexes=[0])]*2,
        participants=[dict(alias="a",classIndex=0,attemptNo=1,attendance="present",cells=[["recorded",50],["missing",None]])],
        expectedTargetCounts=[dict(selectedCount=1,validCount=1,needsCount=1,incompleteCount=1,noEvidenceCount=0,fullCreditCount=0,numerator=1,denominator=1,ratio=1.0)],
        interpretation="失分与资料缺失可重叠；先补齐资料，再通过课堂检测确认具体困难。"),
    case("C04","全部缺考免考","两名唯一学生，一absent一exempt；两人均信息不全且无有效证据，分母0、ratio=null，不写0%或100%。",
        participants=[dict(alias="a",classIndex=0,attemptNo=1,attendance="absent",cells=[["absent",None]]),dict(alias="b",classIndex=0,attemptNo=1,attendance="exempt",cells=[["exempt",None]])],
        selectedParticipantIndexes=[0,1],expectedTargetCounts=[dict(selectedCount=2,validCount=0,needsCount=0,incompleteCount=2,noEvidenceCount=2,fullCreditCount=0,numerator=0,denominator=0,ratio=None)],
        interpretation="无有效成绩证据，不能作能力判断；缺考和免考不能当零分。"),
    case("C05","多知识点综合题","同一综合叶关联两个KP，50/100分别给两个KP关联提示；只证明关联失分，不证明哪个子步骤出错。",
        items=[dict(maxScoreUnits=100,knowledgeIndexes=[0,1])],selectedKnowledgeIndexes=[0,1],expectedTargetCounts=[copy.deepcopy(LOSS),copy.deepcopy(LOSS)],
        interpretation="综合题失分只能关联两个知识点，具体错因尚不能判断。"),
    case("C06","多班报告明确单班","ready报告选两个不同班学生。目标班只有a得50；另一班b得100不进入目标班模型计数。",
        participants=[dict(alias="a",classIndex=0,attemptNo=1,attendance="present",cells=[["recorded",50]]),dict(alias="b",classIndex=1,attemptNo=1,attendance="present",cells=[["recorded",100]])],
        selectedParticipantIndexes=[0,1],interpretation="只解释明确选择的目标班统计；另一班不混入分母。"),
    case("C07","同学生显式选择第二人次","两参测人次同一个学生：第一次50、第二次100；明确只选第二次，所以唯一学生1、有效1、full1、needs0。",
        participants=[dict(alias="a",classIndex=0,attemptNo=1,attendance="present",cells=[["recorded",50]]),dict(alias="a",classIndex=0,attemptNo=2,attendance="present",cells=[["recorded",100]])],
        selectedParticipantIndexes=[1],expectedTargetCounts=[copy.deepcopy(FULL)],interpretation="只依据显式第二人次满分记录，不能把两人次当两个学生或自动取最高分。"),
    case("C08","历史成绩未记录班名","本成绩快照没有班名，固定报告className=null且注明缺失；当前班名仅classNameAtSave，不补成历史事实。",
        interpretation="历史班名未记录，需如实说明；不得拿当前班名补历史事实。"),
    case("C09","题库覆盖缺口","新目标KP无对应正式题，真实suggestions应提供缺口；教案exercises字符串不得伪装成已审核练习对象。",
        items=[dict(maxScoreUnits=100,knowledgeIndexes=[2])],selectedKnowledgeIndexes=[2],questionSource="gap",
        interpretation="题库覆盖不足，请教师补充或审核题目；候选课堂检测文本不是正式题库对象。"),
    case("C10","教材正例常用课时","自写有理数加法片段正面支持符号与绝对值判断，40分钟；真实语义相关性仍由教师评审。",
        selectedFields=["coreCompetencies","keyPoints","teachingDesign","process","exercises"]),
    case("C11","教材边界与五分钟","只提供第一句，支持符号与绝对值，不支持片段之外的运算律证明；5分钟分配2+1+1+1。",
        durationMinutes=5,stageMinutes=[2,1,1,1],materialCase="boundary",
        requirements="五分钟仅复核有理数加法的符号与绝对值判断。所选片段不支持运算律证明，不能编造证明引用。"),
    case("C12","教材范围外主题","固定有理数材料不支持宇宙速度；技术上证据引用合法不代表主题相关或真实模型拒答通过。",
        materialCase="out_of_scope",requestedClaimSupported=False,
        requirements="固定有理数片段不能支持宇宙速度。请明确依据不足，待补充合法物理材料，不得借教材引用编造结论。",
        interpretation="范围外主题没有支持依据，只能说明需补充材料；不编造宇宙速度知识。"),
    case("C13","教材没有所请求依据","提供片段只含加法，未含乘法分配律证明。结构上有evidence不等于支持该论断；与学生noEvidenceCount分开。",
        materialCase="no_claim_evidence",requestedClaimSupported=False,
        requirements="所选加法片段没有乘法分配律证明依据，请说明证据不足，勿伪造教材段落或证明。",
        interpretation="当前片段不支持所请求的证明，需另补合法教材依据。"),
    case("C14","部分字段与教师六字段保持","只应用teachingDesign和process，其余三AI字段及教师title/total/current/type/other/reflection原字节保持。45分钟5+15+20+5。",
        durationMinutes=45,stageMinutes=[5,15,20,5]),
    case("C15","缺失与无证据重叠","仅missing：同一学生既信息不全又无有效证据，二者均1且重叠；有效0、denominator0、ratio=null。",
        participants=[dict(alias="a",classIndex=0,attemptNo=1,attendance="present",cells=[["missing",None]])],
        expectedTargetCounts=[copy.deepcopy(GAPS)],interpretation="没有已记录小题证据；信息不全与无证据不是互斥人数，先补成绩。"),
]

if __name__ == "__main__":
    target = OUT / "case-specs.json"
    if target.exists():
        raise FileExistsError("Do not overwrite handwritten case edition")
    target.write_text(json.dumps(dict(version=1,ruleCode="any_loss_v1",expectedAuthor="independent QA handwriting; not an actual teacher review",copyright="Owned synthetic textbook and questions; no formal student archive or copyrighted supplied textbook copied",cases=cases),ensure_ascii=False,indent=2)+"\n",encoding="utf8",newline="\n")
    print("Prepared 15 handwritten input/oracle cases; teacher_review_pending")
