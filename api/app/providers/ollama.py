"""Local models served by Ollama via LangChain wrappers."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
from ollama import AsyncClient, ResponseError
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool

from app.providers.base import Provider, ProviderError
from app.schemas import ChatMessage, ModelInfo
from app.vision import ollama_vision

SHOW_TIMEOUT_SECONDS = 5.0

# --- Tool Definitions ---
@tool
def get_current_time() -> str:
    """Returns the current local time. Useful when the user asks for the time."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# List of available tools for the agent
AVAILABLE_TOOLS = [get_current_time]

def to_langchain_messages(messages: list[ChatMessage]) -> list[BaseMessage]:
    """Convert Nova ChatMessages to LangChain message objects."""
    out: list[BaseMessage] = []
    for m in messages:
        if m.role == "system":
            out.append(SystemMessage(content=m.content))
        elif m.role == "user":
            content = [{"type": "text", "text": m.content}]
            if m.images:
                for img in m.images:
                    content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img.raw}"}})
            final_content = content if m.images else m.content
            out.append(HumanMessage(content=final_content))
        elif m.role == "assistant":
            out.append(AIMessage(content=m.content))
    return out

def _is_chat_model(item: Any) -> bool:
    """Embedding-only models can't chat, so they stay out of the dropdown."""
    if not item.model:
        return False
    families = (item.details.families or []) if item.details else []
    return not any("bert" in f for f in families) and "embed" not in item.model

class OllamaProvider(Provider):
    id = "ollama"
    label = "Ollama (local)"
    local = True

    def __init__(self, host: str, enabled: bool = True, timeout: float = 120.0) -> None:
        self._host = host
        self._enabled = enabled
        self._client = AsyncClient(host=host, timeout=timeout)
        self._caps_cache: dict[tuple[str, str], list[str] | None] = {}

    @property
    def configured(self) -> bool:
        return self._enabled and bool(self._host)

    async def list_models(self) -> list[ModelInfo]:
        try:
            response = await self._client.list()
        except (httpx.HTTPError, ConnectionError, ResponseError) as exc:
            raise ProviderError(f"Ollama is not reachable at {self._host}") from exc

        items = [item for item in response.models if _is_chat_model(item)]
        capabilities = await self._capabilities(
            [(item.model, getattr(item, "digest", None) or "") for item in items]
        )

        models: list[ModelInfo] = []
        for item in items:
            details = item.details
            families = (details.families or []) if details else []
            models.append(
                ModelInfo(
                    id=item.model,
                    name=item.model.removesuffix(":latest"),
                    provider=self.id,
                    local=True,
                    size_bytes=item.size,
                    parameter_size=details.parameter_size if details else None,
                    family=details.family if details else None,
                    vision=ollama_vision(item.model, capabilities.get(item.model), families),
                )
            )
        return sorted(models, key=lambda m: m.name)

    async def _capabilities(self, models: list[tuple[str, str]]) -> dict[str, list[str] | None]:
        limit = asyncio.Semaphore(4)

        async def one(name: str, digest: str) -> list[str] | None:
            key = (name, digest)
            if digest and key in self._caps_cache:
                return self._caps_cache[key]
            async with limit:
                try:
                    info = await asyncio.wait_for(self._client.show(name), SHOW_TIMEOUT_SECONDS)
                except (httpx.HTTPError, ConnectionError, ResponseError, TimeoutError):
                    return None
                caps = getattr(info, "capabilities", None)
                result = list(caps) if caps is not None else None
                if digest:
                    self._caps_cache[key] = result
                return result

        results = await asyncio.gather(*(one(n, d) for n, d in models))
        return {name: caps for (name, _), caps in zip(models, results, strict=True)}

    async def stream_chat(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Migrated to use LangChain's ChatOllama with Tool Binding."""
        try:
            llm = ChatOllama(
                model=model,
                base_url=self._host,
                temperature=temperature if temperature is not None else 0.7,
            )

            # Tool Binding: Bind available tools to the LLM
            llm_with_tools = llm.bind_tools(AVAILABLE_TOOLS)

            lc_messages = to_langchain_messages(messages)

            # We use a simple loop to handle tool calls (Agentic Loop)
            # For a full production system, LangGraph is recommended.
            current_messages = lc_messages
            max_iterations = 5

            for i in range(max_iterations):
                # Stream the response from the LLM
                full_response_content = ""
                async for chunk in llm_with_tools.astream(current_messages):
                    # If the chunk contains tool calls, we can't stream text normally
                    # but LangChain's astream for tool calls behaves differently.
                    # For simplicity in this provider, we yield text content.
                    if chunk.content:
                        full_response_content += chunk.content
                        yield chunk.content

                # Check if the last message was a tool call
                # Note: astream provides chunks, we need the final message to check tool_calls
                final_msg = await llm_with_tools.ainvoke(current_messages)

                if not final_msg.tool_calls:
                    break

                # Execute tool calls and append results to conversation
                for tool_call in final_msg.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]

                    # Find the tool function
                    tool_fn = next((t for t in AVAILABLE_TOOLS if t.name == tool_name), None)
                    if tool_fn:
                        result = tool_fn.invoke(tool_args)
                        current_messages.append(final_msg) # Add the AI's tool call message
                        current_messages.append(ToolMessage(tool_call_id=tool_call["id"], content=str(result)))
                    else:
                        current_messages.append(ToolMessage(tool_call_id=tool_call["id"], content="Error: Tool not found"))

                # The loop continues to let the LLM process the tool results

        except Exception as exc:
            raise ProviderError(f"Ollama Tool/LangChain error: {str(exc)}") from exc
