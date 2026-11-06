from pelumas_agent.config import get_settings


def main() -> None:
    settings = get_settings()
    failures = []

    if not settings.openai_api_key:
        print("FAIL: OPENAI_API_KEY kosong, isi .env dulu")
        raise SystemExit(1)

    from pelumas_agent.llm.openai_provider import OpenAIClient

    client = OpenAIClient()
    print(f"model: {settings.openai_model}")
    print(f"base_url: {settings.openai_base_url or '(default openai)'}")

    try:
        response = client.complete(
            system="Jawab satu kata saja.", messages=[_message("user", "ping")]
        )
        print(f"[1/3] chat completion OK: {response.text!r}")
    except Exception as error:
        failures.append(f"chat completion: {error}")
        print(f"[1/3] chat completion FAIL: {error}")

    tools = [
        {
            "name": "get_weather",
            "description": "Ambil cuaca sebuah kota.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        }
    ]
    try:
        response = client.complete(
            system="Kamu harus memakai tool yang tersedia.",
            messages=[_message("user", "Berapa cuaca di Jakarta?")],
            tools=tools,
        )
        if response.tool_calls:
            call = response.tool_calls[0]
            print(f"[2/3] tool call OK: {call.name}({call.arguments})")
        else:
            failures.append("tool call: model tidak memanggil tool")
            print(f"[2/3] tool call FAIL: tidak ada tool_calls, text={response.text!r}")
    except Exception as error:
        failures.append(f"tool call: {error}")
        print(f"[2/3] tool call FAIL: {error}")

    from pelumas_agent.llm.embeddings import get_embedder

    embedder = get_embedder()
    try:
        vectors = embedder.embed(["flow meter solar 2 inch"])
        print(f"[3/3] embedding OK: {type(embedder).__name__} dim={len(vectors[0])}")
        if len(vectors[0]) != settings.embed_dim:
            failures.append(
                f"embedding dim {len(vectors[0])} != EMBED_DIM {settings.embed_dim}"
            )
    except Exception as error:
        failures.append(f"embedding: {error}")
        print(f"[3/3] embedding FAIL: {error}")

    if failures:
        print("\nRESULT: FAIL")
        raise SystemExit(1)
    print("\nRESULT: OK")


def _message(role: str, content: str):
    from pelumas_agent.llm.base import LLMMessage

    return LLMMessage(role=role, content=content)


if __name__ == "__main__":
    main()
