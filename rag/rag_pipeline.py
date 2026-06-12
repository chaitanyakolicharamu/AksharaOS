from rag.retriever import Retriever
from rag.context_builder import ContextBuilder
from rag.generator import Generator


class RAGPipeline:
    def __init__(self):
        self.retriever = Retriever()
        self.context_builder = ContextBuilder()
        self.generator = Generator()

    def ask(self, question: str, top_k: int = 5) -> str:
        results = self.retriever.retrieve(question, top_k=top_k)
        context = self.context_builder.build(results)
        answer = self.generator.generate(question, context)
        return answer


if __name__ == "__main__":
    question = input("Ask Bangaru Palukulu: ")

    rag = RAGPipeline()
    answer = rag.ask(question)

    print("\n" + "=" * 80)
    print("ANSWER")
    print("=" * 80)
    print(answer)
