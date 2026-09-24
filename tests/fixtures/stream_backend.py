"""隔离的真实 HTTP 上游 + 正式 FastAPI，固定测试数据，不读取用户配置。"""
import json
import sys
import tempfile
import threading
import time
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'apps/api'))
import uvicorn
from app.main import create_app
from app.core.config import Settings
from app.core.secrets import SecretStore
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.model_config import ModelConnection,ModelProfile,now_utc

gate = threading.Event()
answer_gate = threading.Event()
reasoning_gate = threading.Event()
content_gate = threading.Event()
stats = {'first':None,'last':None,'cancelled':False,'bodyRaw':'','bodyDeltas':[],'reasoningRaw':'','reasoningDeltas':[]}
ANSWER = '''## 从现象理解概念

这是一段用于验收的**中文分块回答**。先观察，再解释。

1. 明确研究对象
2. 比较不同情境
3. 用证据检验结论

### 数学表达

$$E = mc^2$$

| 阶段 | 学习目标 | 教学活动 |
| --- | --- | --- |
| 观察 | 发现差异 | 描述实验现象 |
| 解释 | 建立联系 | 分组讨论与归纳 |

```python
def energy(mass):
    return mass * 299792458 ** 2
```

'''

class Upstream(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        if self.path.startswith('/answer'): answer_gate.set(); body={'ok':True}
        elif self.path.startswith('/reasoning'): reasoning_gate.set(); body={'ok':True}
        elif self.path.startswith('/content'): content_gate.set(); body={'ok':True}
        elif self.path.startswith('/release'): gate.set(); content_gate.set(); body={'ok':True}
        elif self.path.startswith('/stats'): body=stats
        else: body={'data':[{'id':'teaching-alpha'},{'id':'teaching-beta'},{'id':'teaching-beta'}]}
        data=json.dumps(body).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if not body.get('stream'):
            data=json.dumps({'choices':[{'message':{'content':'连接正常'},'finish_reason':'stop'}]}).encode()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return
        gate.clear(); answer_gate.clear(); reasoning_gate.clear(); content_gate.clear(); stats.update(first=None,last=None,cancelled=False,bodyRaw='',bodyDeltas=[],reasoningRaw='',reasoningDeltas=[])
        self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.send_header('Cache-Control','no-cache'); self.end_headers()
        kind='responses' if self.path.endswith('/responses') else 'anthropic' if self.path.endswith('/messages') else 'chat'
        def emit(name,payload):
            wire=(('event: '+name+'\n') if name else '')+'data: '+json.dumps(payload,ensure_ascii=False)+'\n\n'
            self.wfile.write(wire.encode()); self.wfile.flush()
        def text(value):
            stats['bodyRaw'] += value
            stats['bodyDeltas'].append(value)
            if kind=='chat': emit('',{'choices':[{'delta':{'content':value}}]})
            elif kind=='responses': emit('response.output_text.delta',{'delta':value})
            else: emit('content_block_delta',{'delta':{'type':'text_delta','text':value}})
        def body_delta(value):
            text(value)
            time.sleep(.12)
        def reasoning_delta(value):
            stats['reasoningRaw'] += value
            stats['reasoningDeltas'].append(value)
            if kind == 'chat': emit('', {'choices': [{'delta': {'reasoning_content': value}}]})
            elif kind == 'responses': emit('response.reasoning_summary_text.delta', {'delta': value})
            else: emit('content_block_delta', {'delta': {'type': 'thinking_delta', 'thinking': value}})
        try:
            performance_prompt = json.dumps(body, ensure_ascii=False)
            if '性能验收20k' in performance_prompt or '性能验收50k' in performance_prompt:
                target = 20_000 if '性能验收20k' in performance_prompt else 50_000
                piece = '性能推理段落：先比较变量与约束，再验证边界；' + '推导证据并检查结论是否保持稳定。' * 12 + '得到 $x^2+y^2=z^2$。'
                reasoning = (piece + '\n\n') * (target // (len(piece) + 2)) + (piece + '\n\n')[:target % (len(piece) + 2)]
                if len(reasoning) != target:
                    raise AssertionError(f'性能样本长度错误：{len(reasoning)} != {target}')
                stats['reasoningRaw'] = reasoning
                stats['reasoningDeltas'] = []
                stats['first'] = time.monotonic()
                for offset in range(0, len(reasoning), 256):
                    delta = reasoning[offset:offset + 256]
                    stats['reasoningDeltas'].append(delta)
                    if kind == 'chat': emit('', {'choices': [{'delta': {'reasoning_content': delta}}]})
                    elif kind == 'responses': emit('response.reasoning_summary_text.delta', {'delta': delta})
                    else: emit('content_block_delta', {'delta': {'type': 'thinking_delta', 'thinking': delta}})
                    time.sleep(.012)
                answer = ('正文公式：$a^2+b^2=c^2$，块级：\n\n$$\nE=mc^2\n$$\n\n' * 40)
                for offset in range(0, len(answer), 96):
                    body_delta(answer[offset:offset + 96])
                stats['last'] = time.monotonic()
                if kind=='chat': emit('',{'choices':[{'delta':{},'finish_reason':'stop'}]}); self.wfile.write(b'data: [DONE]\n\n')
                elif kind=='responses': emit('response.completed',{'response':{'status':'completed'}})
                else: emit('message_delta',{'delta':{'stop_reason':'end_turn'}}); emit('message_stop',{})
                return
            if '正文后继续推理验收' in json.dumps(body, ensure_ascii=False):
                stats['reasoningRaw'] = ''
                stats['reasoningDeltas'] = []
                for index in range(8):
                    value = f'正文前推理行 {index:02d}：分析背景条件和关键变量。\n'
                    stats['reasoningRaw'] += value
                    stats['reasoningDeltas'].append(value)
                    if kind == 'chat': emit('', {'choices': [{'delta': {'reasoning_content': value}}]})
                    elif kind == 'responses': emit('response.reasoning_summary_text.delta', {'delta': value})
                    else: emit('content_block_delta', {'delta': {'type': 'thinking_delta', 'thinking': value}})
                    time.sleep(.12)
                text('正文已开始，推理仍在继续。\n\n')
                for index in range(48):
                    value = f'正文后推理行 {index:02d}：继续解释推导并核对过程细节。\n'
                    stats['reasoningRaw'] += value
                    stats['reasoningDeltas'].append(value)
                    if kind == 'chat': emit('', {'choices': [{'delta': {'reasoning_content': value}}]})
                    elif kind == 'responses': emit('response.reasoning_summary_text.delta', {'delta': value})
                    else: emit('content_block_delta', {'delta': {'type': 'thinking_delta', 'thinking': value}})
                    time.sleep(.12)
                stats['first'] = time.monotonic()
                while not gate.wait(.1):
                    self.wfile.write(b': heartbeat\n\n'); self.wfile.flush()
                if kind=='chat': emit('',{'choices':[{'delta':{},'finish_reason':'stop'}]}); self.wfile.write(b'data: [DONE]\n\n')
                elif kind=='responses': emit('response.completed',{'response':{'status':'completed'}})
                else: emit('message_delta',{'delta':{'stop_reason':'end_turn'}}); emit('message_stop',{})
                return
            if '推理跟随验收' in json.dumps(body, ensure_ascii=False):
                stats['reasoningRaw'] = ''
                stats['reasoningDeltas'] = []
                for index in range(48):
                    value = f'推理行 {index:02d}：持续解释新概念与因果关系，观察变量变化并记录证据。\n'
                    stats['reasoningRaw'] += value
                    stats['reasoningDeltas'].append(value)
                    if kind == 'chat': emit('', {'choices': [{'delta': {'reasoning_content': value}}]})
                    elif kind == 'responses': emit('response.reasoning_summary_text.delta', {'delta': value})
                    else: emit('content_block_delta', {'delta': {'type': 'thinking_delta', 'thinking': value}})
                    time.sleep(.12)
                value = '最新推理内容标记：FOLLOW-END。'
                stats['reasoningRaw'] += value
                stats['reasoningDeltas'].append(value)
                if kind == 'chat': emit('', {'choices': [{'delta': {'reasoning_content': value}}]})
                elif kind == 'responses': emit('response.reasoning_summary_text.delta', {'delta': value})
                else: emit('content_block_delta', {'delta': {'type': 'thinking_delta', 'thinking': value}})
                deadline = time.monotonic() + 25
                while not gate.wait(.1) and time.monotonic() < deadline:
                    self.wfile.write(b': heartbeat\n\n'); self.wfile.flush()
            if '推理验收' in json.dumps(body, ensure_ascii=False):
                chunks = [
                    r'先分析公式 \(a^2+b^2=c^2\)，再给出结论。' + '\n\n',
                    '块级公式：\n\n$$\nE = mc^2\n$$\n\n',
                    '反斜杠块级：\n\n\\[\\sum_{i=1}^{n} i\\]\n\n',
                    '代码里的美元符号保持原文：\n\n```sh\necho "$HOME 与 $((1+2))"\n```\n\n',
                    '未闭合的尾段 $x + y',
                ]
                for chunk_value in chunks:
                    reasoning_delta(chunk_value)
                    self.wfile.flush()
                    time.sleep(.02)
                deadline = time.monotonic() + 25
                while not reasoning_gate.wait(.1) and time.monotonic() < deadline:
                    self.wfile.write(b': heartbeat\n\n'); self.wfile.flush()
                reasoning_delta(' = z$ 补齐。\n\n')
                deadline = time.monotonic() + 25
                while not answer_gate.wait(.1) and time.monotonic() < deadline:
                    self.wfile.write(b': heartbeat\n\n'); self.wfile.flush()
                answer = r'结论：\(a^2+b^2=c^2\)。' + '\n\n' + r'\[\frac{1}{2}+\sqrt{x}\]' + '\n\n'
                stats['bodyRaw'] += answer
                stats['bodyDeltas'].append(answer)
                if kind=='chat': emit('', {'choices':[{'delta':{'content':answer}}]})
                elif kind=='responses': emit('response.output_text.delta', {'delta':answer})
                else: emit('content_block_delta', {'delta':{'type':'text_delta','text':answer}})
            if '正文公式验收' in json.dumps(body, ensure_ascii=False):
                body_chunks = [
                    r'正文闭合公式 $x^2+y^2=z^2$ 与 \(a^2+b^2=c^2\)。' + '\n\n',
                    r'块公式开始 $$E = mc^2$$ 与 \[\frac{1}{2}\]。' + '\n\n',
                    r'- 列表公式 $\alpha+\beta$' + '\n' + r'- 另一项 \(x_1\)' + '\n\n',
                    '| 项目 | 公式 |\n| --- | --- |\n| 能量 | $E=mc^2$ |\n\n',
                    r'矩阵推导：' + '\n\n' + r'$$' + '\n' + r'\begin{aligned}' + '\n' + r'u &= v + at \\' + '\n' + r'v &= v_0 + at' + '\n' + r'\end{aligned}' + '\n' + r'$$' + '\n\n',
                    '代码美元原样：\n\n```sh\necho "$HOME $((1+2))"\n```\n\n',
                    r'单反斜杠 \(q\)，双反斜杠公式 \\(r^2\\)。尾段未闭合 $x+y',
                ]
                for piece in body_chunks:
                    body_delta(piece)
                deadline = time.monotonic() + 25
                while not content_gate.wait(.1) and time.monotonic() < deadline:
                    self.wfile.write(b': heartbeat\n\n'); self.wfile.flush()
                body_delta(' = z$ 已补齐。')
                deadline = time.monotonic() + 25
                while not gate.wait(.1) and time.monotonic() < deadline:
                    self.wfile.write(b': heartbeat\n\n'); self.wfile.flush()
            stats['first']=time.monotonic(); text('第一段中文已经到达。\n\n')
            deadline=time.monotonic()+25
            while not gate.wait(.1) and time.monotonic()<deadline:
                self.wfile.write(b': heartbeat\n\n'); self.wfile.flush()
            if '长回答' in json.dumps(body,ensure_ascii=False):
                for _ in range(6): text(ANSWER); time.sleep(.03)
            text('最后一段已释放。'); stats['last']=time.monotonic()
            if kind=='chat': emit('',{'choices':[{'delta':{},'finish_reason':'stop'}]}); self.wfile.write(b'data: [DONE]\n\n')
            elif kind=='responses': emit('response.completed',{'response':{'status':'completed','usage':{'input_tokens':9,'output_tokens':12}}})
            else: emit('message_delta',{'delta':{'stop_reason':'end_turn'},'usage':{'output_tokens':12}}); emit('message_stop',{})
            self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError,OSError): stats['cancelled']=True

server=ThreadingHTTPServer(('127.0.0.1',8002),Upstream)
threading.Thread(target=server.serve_forever,daemon=True).start()
temporary=tempfile.TemporaryDirectory(prefix='zqky-chat-test-')
repo=ModelConfigRepository(Path(temporary.name)/'model-config.json'); secrets=SecretStore()
for index,protocol in enumerate(['openai-chat','openai-responses','anthropic-messages']):
    cid='c'+str(index); pid='p'+str(index)
    repo.create_connection(ModelConnection(id=cid,displayName=['教学模型服务','Responses 服务','Anthropic 服务'][index],protocol=protocol,baseUrl='http://127.0.0.1:8002/v1',createdAt=now_utc(),updatedAt=now_utc()))
    secrets.put(cid,'synthetic-test-key')
    repo.create_profile(ModelProfile(id=pid,connectionId=cid,displayName=['教学问答模型','Responses 模型','Anthropic 模型'][index],modelId='teaching-alpha',purpose='chat',contextTokens=32000,maxOutputTokens=2048,createdAt=now_utc(),updatedAt=now_utc()))
repo.mutate(lambda d:setattr(d,'defaultChatProfileId','p0'))
os.environ['ZQKY_API_PORT']='8001'
os.environ['ZQKY_ENV']='test'
settings=Settings.from_env()
app=create_app(settings,repository=repo,secret_store=secrets)
if __name__=='__main__':
    try: uvicorn.run(app,host='127.0.0.1',port=8001,log_level='warning')
    finally: server.shutdown(); temporary.cleanup()
