"""Quick smoke test to verify Azure OpenAI connectivity."""
import os
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY", ""),
    api_version="2025-01-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
)

print("Sending test prompt to Azure OpenAI GPT-4o...")
try:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Reply with exactly: CONNECTION OK"}],
        max_tokens=10
    )
    reply = response.choices[0].message.content.strip()
    print(f"SUCCESS - Response: {reply}")
    print(f"   Model: {response.model}")
    print(f"   Tokens used: {response.usage.total_tokens}")
except Exception as e:
    print(f"FAILED - Connection error: {e}")
