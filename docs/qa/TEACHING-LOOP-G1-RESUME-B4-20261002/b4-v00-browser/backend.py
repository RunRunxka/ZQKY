"""CTRL alone owns listening lifecycle. Only model port is a controlled double."""
import asyncio
import json
from dataclasses import asdict
from isolation import isolated_settings
settings=isolated_settings()
seed=json.loads((settings.data_dir.parent/"browser-seed.json").read_text(encoding="utf-8"))
assert seed["dataDir"]==str(settings.data_dir)
from app.main import create_app, _build_executor_registry
from app.core.secrets import SecretStore
from app.providers.llm.base import FINISH_STOP, LLMConfig, LLMResponse
from app.schemas.model_config import ApiFormat, ModelConnection, ModelProfile, ModelProtocol, now_utc
from app.services.model_runtime import ChatModelHandle
from app.services.question_bank.service import build_question_bank_service

PROFILE="b4-v00-controlled-profile"
CONNECTION="b4-v00-controlled-connection"
GENERATED="手动补题：计算 (-2)+5 的结果。"


class ControlledProvider:
    def __init__(self):
        self.calls=[];self.gate=None;self.released=False

    async def complete(self, config, request, *, transport=None):
        actual=asdict(request)
        # Only the synthetic request and profile/model identity; never config
        # credentials, auth headers, secret stores or external requests.
        self.calls.append(dict(profileId=config.modelProfileId,modelId=config.modelId,request=actual))
        self.gate=asyncio.Event()
        if self.released:self.gate.set()
        await self.gate.wait()
        return LLMResponse(text=json.dumps({"questions":[dict(type="short_answer",stemMarkdown=GENERATED,options=[],answer=dict(choiceKeys=[],accepted=None,textMarkdown="3"),explanationMarkdown="按数轴计算，得到3。",knowledgePointIds=[seed["points"][0]["id"]],evidenceIds=[],assetIds=[])]},ensure_ascii=False),finishReason=FINISH_STOP)

    def release(self):
        self.released=True
        if self.gate is not None:self.gate.set()


app=create_app(settings,secret_store=SecretStore())
provider=ControlledProvider();timestamp=now_utc();repo=app.state.model_config_repo
repo.create_connection(ModelConnection(id=CONNECTION,displayName="B4受控技术链",protocol=ModelProtocol.openai_chat,providerId="ollama",apiFormat=ApiFormat.openai_chat,baseUrl="http://127.0.0.1:9/v1",createdAt=timestamp,updatedAt=timestamp))
repo.create_profile(ModelProfile(id=PROFILE,connectionId=CONNECTION,displayName="B4隔离补题模型",modelId="b4-v00-model",purpose="chat",maxOutputTokens=2048,createdAt=timestamp,updatedAt=timestamp))
repo.mutate(lambda document:setattr(document,"defaultChatProfileId",PROFILE))
handle=ChatModelHandle(profile_id=PROFILE,model_id="b4-v00-model",provider=provider,config=LLMConfig(protocol=ModelProtocol.openai_chat,baseUrl="http://127.0.0.1:9/v1",modelId="b4-v00-model",apiFormat=ApiFormat.openai_chat.value,connectionId=CONNECTION,modelProfileId=PROFILE))


def resolver(profile_id):
    if profile_id!=PROFILE:raise RuntimeError("Unexpected QA model profile")
    return handle


app.state.question_bank_service=build_question_bank_service(app.state.question_bank,settings,model_resolver=resolver,knowledge_catalog=app.state.knowledge,coordinator=app.state.publication_coordinator,job_engine=app.state.job_engine)
_build_executor_registry(app)


@app.get("/__test/b4",include_in_schema=False)
async def metadata():
    return dict(seed=seed,profileId=PROFILE,generatedStem=GENERATED,calls=provider.calls,released=provider.released)


@app.post("/__test/b4/release",include_in_schema=False)
async def release():
    provider.release();return {"released":True}
