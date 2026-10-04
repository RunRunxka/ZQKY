"""Offline review/preflight. Never opens network, imports main or reads .env.

Live calls remain CTRL-owned through existing Provider after explicit user scope.
Missing profile/model/cases/number/budget refuses even preflight readiness.
This tool cannot execute paid calls or invent teacher marks.
"""
import argparse
import json
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument("--scope",type=Path,required=True)
args=parser.parse_args()
scope=json.loads(args.scope.read_bytes())
missing=[]
for field in ["modelProfileId","modelId","caseIds","sampleCount"]:
    if not scope.get(field):missing.append(field)
if not scope.get("maxTotalTokens") and scope.get("maxCostCny") is None:missing.append("maxTotalTokens or maxCostCny")
if scope.get("caseIds") and scope.get("sampleCount")!=len(scope["caseIds"]):missing.append("sampleCount must equal explicit caseIds count")
if scope.get("maxTotalTokens") is not None and (type(scope["maxTotalTokens"]) is not int or scope["maxTotalTokens"]<=0):missing.append("positive integer token ceiling")
if scope.get("maxCostCny") is not None and (type(scope["maxCostCny"]) not in {int,float} or scope["maxCostCny"]<=0):missing.append("positive cost ceiling")
if any(key.lower() in {"apikey","api_key","secret","credential"} for key in scope):missing.append("credentials prohibited in non-sensitive scope file")
if missing:
    print(json.dumps(dict(status="LIVE_REFUSED_MISSING_OR_INVALID_SCOPE",missing=missing,networkCalls=0,mainImported=False,formalEnvRead=False,liveRun="待输入",teacherReview="teacher_review_pending"),ensure_ascii=False))
    raise SystemExit(2)
print(json.dumps(dict(status="SCOPE_REVIEW_READY_CTRL_EXECUTION_REQUIRED",networkCalls=0,mainImported=False,formalEnvRead=False,
    message="Use the existing runtime profile/resolver/anonymous whitelist/provider pipeline; no alternate prompt or model. Human scope authorization and budget enforcement remain CTRL responsibilities.",teacherReview="teacher_review_pending"),ensure_ascii=False))
