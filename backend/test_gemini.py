from app.llm import understand

history = [
    {
        "role": "user",
        "content": "I need an apartment in Chennai."
    },
    {
        "role": "assistant",
        "content": "What is your budget?"
    },
    {
        "role": "user",
        "content": "My budget is 80 lakhs."
    }
]

result = understand(
    provider="gemini",
    history=history,
    current="I need 2 BHK."
)

print(result.model_dump_json(indent=2))