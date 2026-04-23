import os
from typing import Any, Dict, List, Optional
from groq import AsyncGroq
from cerebras.cloud.sdk import AsyncCerebras
from agents.lib.logging import log_step

_groq_client: Optional[AsyncGroq] = None
_cerebras_client: Optional[AsyncCerebras] = None

def get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY must be set")
        _groq_client = AsyncGroq(api_key=api_key)
    return _groq_client

def get_cerebras_client() -> AsyncCerebras:
    global _cerebras_client
    if _cerebras_client is None:
        api_key = os.environ.get("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY must be set")
        _cerebras_client = AsyncCerebras(api_key=api_key)
    return _cerebras_client

async def complete(
    messages: List[Dict[str, str]],
    job_id: str,
    agent_name: str,
    video_id: Optional[str] = None,
    **kwargs: Any
) -> str:
    """
    LLM completion with Groq-to-Cerebras failover.
    """
    try:
        # Try Groq first
        client = get_groq_client()
        response = await client.chat.completions.create(
            model=kwargs.get("model", "llama-3.1-70b-versatile"),
            messages=messages,
            temperature=kwargs.get("temperature", 0.3),
            response_format=kwargs.get("response_format"),
            max_tokens=kwargs.get("max_tokens", 1024),
        )
        return response.choices[0].message.content
    except Exception as e:
        await log_step(
            job_id=job_id,
            agent=agent_name,
            step="fallback",
            message=f"Groq failed, falling back to Cerebras: {str(e)}",
            video_id=video_id
        )

        # Fallback to Cerebras
        client = get_cerebras_client()
        # Ensure we pass all relevant kwargs to the fallback
        fallback_params = {
            "model": kwargs.get("fallback_model", "llama3.1-70b"),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }

        # Cerebras might have different param names or support for response_format
        if "response_format" in kwargs:
            fallback_params["response_format"] = kwargs["response_format"]

        response = await client.chat.completions.create(**fallback_params)
        return response.choices[0].message.content
