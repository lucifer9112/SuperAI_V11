---
name: rag-engineer
description: RAG system design - retrieval, chunking, embedding, vector stores, reranking
triggers: [rag, retrieval, embedding, vector, chunk, chromadb, pinecone, faiss, search]
category: ai-ml
auto_activate: true
priority: 7
---

# RAG Engineer

## RAG Pipeline
1. **Ingest** — load documents, split into chunks
2. **Embed** — convert chunks to vectors
3. **Store** — index in vector database
4. **Retrieve** — semantic search for relevant chunks
5. **Augment** — inject retrieved context into prompt
6. **Generate** — LLM produces answer grounded in context

## Chunking Strategies
| Strategy | Best For | Chunk Size |
|----------|---------|------------|
| Fixed-size | Simple docs | 500-1000 tokens |
| Semantic | Complex docs | Variable |
| Recursive | Code/structured | By section |
| Sentence | Conversations | 3-5 sentences |

## Embedding Best Practices
- Use task-specific models (retrieval vs classification)
- Normalize vectors before storing
- Include metadata (source, page, timestamp)
- Batch embedding for efficiency

## Retrieval Optimization
- Hybrid search (keyword + semantic)
- Reranking with cross-encoder
- Max Marginal Relevance for diversity
- Retrieve more, then filter (over-retrieve → rerank)

Source: antigravity-awesome-skills
