import ollama


class Generator:

    def __init__(self, model_name="qwen2.5:7b-instruct"):
        self.model_name = model_name

    def generate(self, question: str, context: str):

        prompt = f"""
You are Bangaru Palukulu AI.

Task:
Answer the user's question using ONLY the given context.

Rules:
1. Do not repeat the same idea.
2. Do not invent information.
3. If OCR text is unclear, simplify it.
4. Answer in natural Telugu.
5. Maximum 5 bullet points.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""

        response = ollama.chat(
            model=self.model_name, messages=[{"role": "user", "content": prompt}]
        )

        return response["message"]["content"]
