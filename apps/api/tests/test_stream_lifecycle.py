import asyncio
import httpx2 as httpx
import pytest
from contextlib import aclosing
from app.providers.llm.openai_chat import OpenAIChatProvider
from app.providers.llm.base import ProviderError
from app.schemas.model_config import ModelProtocol
from tests.test_providers_stream import make_config,make_request,sse_response

async def test_start_precedes_first_token_and_close_is_immediate():
    opened = asyncio.Event()
    class Stream(httpx.AsyncByteStream):
        closed = False
        async def __aiter__(self):
            opened.set()
            await asyncio.Event().wait()
            yield b''
        async def aclose(self): self.closed = True
    stream = Stream()
    transport = httpx.MockTransport(lambda r:httpx.Response(200,headers={'content-type':'text/event-stream'},stream=stream))
    generator = OpenAIChatProvider().stream(make_config(ModelProtocol.openai_chat),make_request(),transport=transport)
    assert (await generator.__anext__()).type == 'start'
    assert not opened.is_set()
    await generator.aclose()
    assert stream.closed

async def test_json_response_rejected_before_start():
    transport = httpx.MockTransport(lambda r:httpx.Response(200,json={'choices':[]}))
    with pytest.raises(ProviderError) as e:
        await OpenAIChatProvider().stream(make_config(ModelProtocol.openai_chat),make_request(),transport=transport).__anext__()
    assert e.value.code == 'UPSTREAM_PROTOCOL_ERROR'

async def test_eof_without_terminal_is_not_success():
    transport = sse_response([b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'])
    events = []
    with pytest.raises(ProviderError) as e:
        async with aclosing(OpenAIChatProvider().stream(make_config(ModelProtocol.openai_chat),make_request(),transport=transport)) as stream:
            async for event in stream: events.append(event)
    assert e.value.code == 'STREAM_INTERRUPTED'
    assert [x.type for x in events] == ['start','text']
