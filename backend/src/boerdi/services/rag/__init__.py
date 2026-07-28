"""RAG-Paket (P6, spec §4-Baum: ``services/rag/retrieval.py``).

Bündelt den Retrieval-Pfad der Wissensbereiche: ``retrieval`` löst die
Retrieval-Parameter auf (ENV > yaml-area > Defaults) und trägt später die
pgvector-Cosine-Suche + die Area-Modi (always/on-demand aus ``rag-config``).
Die Embedding-Boundary ist ``services/llm.embedding`` (LiteLLM) — in den
Retrieval-Tests gefakt. Reine Chunking-Logik liegt framework-frei in
``domain/rag_chunking``.
"""
