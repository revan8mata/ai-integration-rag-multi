from config import settings
from google import genai
from openai import AsyncOpenAI
from google.genai import types
from config import settings
from anthropic import AsyncAnthropic

gemini_client = genai.Client(api_key=settings.api_key)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
claude_client = AsyncAnthropic(api_key=settings.anthropic_api_key)



# def format_for_Anthropic(contents):



def format_for_Anthropic_openai(contents):
    # if isinstance(contents, str):
    #     return [{"role": "user", "content": contents}]
    messages = []
    for msg in contents:
        messages.append({
            "role": "assistant" if msg["role"] == "model" else msg["role"],
            "content": msg["parts"][0]["text"]
        })
    return messages


async def generate_stream(contents, provider: str = "gemini"):
    if provider == "gemini":
        async for chunk in await gemini_client.aio.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=contents
        ):
            text = chunk.text or ""
            token_count = chunk.usage_metadata.total_token_count if chunk.usage_metadata else None
            yield (text, token_count)

    elif provider == "openai":
        formatted = format_for_Anthropic_openai(contents)
        async for chunk in await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=formatted,
            stream=True,
            stream_options={"include_usage": True}   #needed this . makes sure meta data is included
        ):
            text = chunk.choices[0].delta.content or ""
            token_count = chunk.usage.total_tokens if chunk.usage else None
            yield (text, token_count)
    elif provider == "Anthropic":

        formatted = format_for_Anthropic_openai(contents)

        async with claude_client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=formatted
        ) as stream:

            async for text in stream.text_stream:
                yield (text, None)

            final_message = await stream.get_final_message()

            total_tokens = (
                    final_message.usage.input_tokens +
                    final_message.usage.output_tokens
            )

            yield ("", total_tokens)


    else:
        raise ValueError(f"unknown provider: {provider}")