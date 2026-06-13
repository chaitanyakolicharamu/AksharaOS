import requests


class Generator:
    def __init__(self, model_name: str = "qwen2.5:3b"):
        self.model_name = model_name
        self.base_url = "http://localhost:11434/api/generate"

    def build_prompt(self, query: str, context: str) -> str:
        return f"""
You are AksharaOS, a Telugu language knowledge assistant.

Answer the user using ONLY the provided context.
If the answer is not in the context, say that the available sources do not contain enough information.

User question:
{query}

Context:
{context}

Answer in clear Telugu. If useful, include short bullet points.
"""

    def generate(self, query: str, context: str) -> str:
        prompt = self.build_prompt(query=query, context=context)

        response = requests.post(
            self.base_url,
            json={
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )

        response.raise_for_status()
        return response.json()["response"].strip()
