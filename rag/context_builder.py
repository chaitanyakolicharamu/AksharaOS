class ContextBuilder:

    def build(self, retrieval_results):

        documents = retrieval_results["documents"][0]

        context = "\n\n".join(documents)

        return context
