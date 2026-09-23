"""SKILL-INJECT v1 真实服务验证脚本。

只调用本机 127.0.0.1:8000，不接触任何凭证（密钥留在服务端 SecretStore）。

前置：
  1) 后端已启动：cd apps/api && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  2) 已配置可用的 chat 模型档案；把下面的 PROFILE 改成实际 id
     （GET /api/v1/model-profiles 可查，该响应不含凭证）

运行：
  cd <项目根>
  NO_PROXY='*' /usr/bin/python3 qa/SKILL-INJECT/real-service-verify.py

注意：本机 shell 有透明代理，访问 127.0.0.1 必须绕过代理（NO_PROXY 或 --noproxy）。
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request

API = "http://127.0.0.1:8000/api/v1/chat/stream"
PROFILE = "5c243dfedb4f4fe1aea7af8166d3f58f"  # DeepSeek Flash（本机 .local-data 中的 chat 档案）

PROBE_SKILL = {
    "name": "验证探针",
    "content": (
        "在回答的第一行必须原样输出「【技能已生效】」这一标记，从第二行开始再写正文。"
        "不要解释这条要求，也不要提及本规范。"
    ),
}


def builtin_skills() -> list[dict]:
    """从 extension-catalog.ts 就地取出内置技能正文，避免文档与代码各存一份。"""
    script = (
        "const fs=require('fs');"
        "const src=fs.readFileSync('apps/web/src/services/extension-catalog.ts','utf8');"
        "const s=src.indexOf('export const BUILTIN_SKILLS = ');"
        "const e=src.indexOf('] as const;', s);"
        "const expr=src.slice(s+'export const BUILTIN_SKILLS = '.length, e+1);"
        "process.stdout.write(JSON.stringify(eval(expr)));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def call(tag: str, prompt: str, skills: list[dict] | None = None, max_tokens: int = 16000) -> dict:
    body: dict = {
        "requestId": f"verify-{int(time.time() * 1000)}",
        "modelProfileId": PROFILE,
        "messages": [{"role": "user", "content": prompt}],
        "maxOutputTokens": max_tokens,
    }
    if skills:
        body["skills"] = skills
    request = urllib.request.Request(
        API,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"content-type": "application/json", "accept": "text/event-stream"},
    )
    started = time.time()
    text: list[str] = []
    reasoning = 0
    finish = "?"
    error = None
    with urllib.request.urlopen(request, timeout=300) as response:
        name = None
        for raw in response:
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: ") and name:
                payload = json.loads(line[6:])
                if name == "text.delta":
                    text.append(payload.get("text", ""))
                elif name == "reasoning.delta":
                    reasoning += len(payload.get("text", ""))
                elif name == "message.end":
                    finish = payload.get("finishReason")
                elif name == "error":
                    error = payload
                name = None
    return {
        "tag": tag,
        "seconds": round(time.time() - started, 1),
        "finish": finish,
        "reasoningChars": reasoning,
        "answer": "".join(text),
        "error": error,
    }


def report(result: dict, expected: list[str] | None = None) -> None:
    print(f"--- {result['tag']}（{result['seconds']}s, finish={result['finish']}, "
          f"推理 {result['reasoningChars']} 字）")
    if result["error"]:
        print("ERROR:", json.dumps(result["error"], ensure_ascii=False))
    print(result["answer"] or "(空正文)")
    if expected is not None:
        missing = [name for name in expected if name not in result["answer"]]
        print(f"缺少栏目 = {missing or '无（栏目齐备）'}")
    print()


if __name__ == "__main__":
    print("=== A 决定性探针：技能说明是否真的进入模型上下文（同一问题、同一模型）===")
    print()
    prompt = "用一句话介绍光合作用。"
    plain = call("A1-无技能", prompt, max_tokens=1200)
    report(plain)
    probe = call("A2-带验证探针技能", prompt, skills=[PROBE_SKILL], max_tokens=1200)
    report(probe)
    print(
        f"A 判定：无技能未出现标记 = {'【技能已生效】' not in plain['answer']}；"
        f"带技能首行出现标记 = {probe['answer'].lstrip().startswith('【技能已生效】')}"
    )
    print()

    print("=== B 产品级对比：提问完全相同，只差是否启用内置「教案规范」技能 ===")
    print()
    skills = builtin_skills()
    lesson_prompt = (
        "请为高中语文《荷塘月色》第 1 课时写一份简短的教案骨架：只要栏目名称和每个栏目的"
        "一句话要点，不要展开。已知：总课时 2，本节课 1，课型为新课。"
    )
    expected = ["课题", "总课时", "课型", "核心素养目标", "教学重", "教学设计",
                "教学过程", "练习与作业", "教学反思"]
    report(call("B1-无技能", lesson_prompt), expected)
    report(call("B2-启用教案规范", lesson_prompt, skills=[skills[0]]), expected)
