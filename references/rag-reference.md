# Contextual Retrieval Reference

## Why Naive RAG Fails

Chunks lose context during embedding. "The revenue increased by 12%" becomes meaningless without knowing which company, which period, which metric. The fix: add context before encoding.

## Contextual Retrieval Pipeline

```
Document
  → Split into 500-token chunks (50-token overlap)
  → For each chunk, generate 50-100 token context with Haiku:
      "This chunk is from [doc title]. It describes [what this chunk covers]
       in the context of [broader document topic]."
  → Store: context + chunk (combined) in both:
      • Vector index (semantic search)
      • BM25 index (keyword search)

At query time:
  → Run hybrid retrieval (top-20 from each index)
  → Deduplicate + merge
  → Rerank to top-5
  → Use top-5 as context
```

## Implementation Sketch

```python
def enrich_chunk(chunk, doc_title, doc_summary):
    """Add context to chunk before indexing. Use Haiku for cost."""
    context = haiku.complete(f"""
    Document: {doc_title}
    Summary: {doc_summary[:200]}

    Chunk: {chunk}

    Write 2-3 sentences: what is this chunk about, how does it fit the document?
    Be specific. Include key entities and relationships.
    """)
    return f"{context}\n\n{chunk}"

# Build index
for chunk in chunks:
    enriched = enrich_chunk(chunk, title, summary)
    vector_index.add(enriched, metadata={"chunk_id": id})
    bm25_index.add(enriched, metadata={"chunk_id": id})

# Query
def retrieve(query, top_k=5):
    v_results = vector_index.search(query, k=20)
    b_results = bm25_index.search(query, k=20)
    combined = deduplicate(v_results + b_results)
    return reranker.rerank(combined, query)[:top_k]
```

## Failure Rate Reduction

| Method | Failure Rate | Reduction |
|--------|-------------|-----------|
| Baseline RAG | 5.7% | — |
| + Contextual embeddings | 3.7% | -35% |
| + BM25 hybrid | 2.9% | -49% |
| + Reranking | 1.9% | -67% |

## Cost Optimization

Use **prompt caching** for the document corpus in the context generation step:

```python
# Cache the document corpus as a system prompt prefix
# Subsequent chunk context generation hits the cache
# Cost: ~$1.02/M tokens vs $15/M without caching
```

**Model selection:**
- Context generation: Haiku (cheap, fast, mechanical task)
- Reranking: Sonnet or dedicated reranker (quality matters)
- Final answer: Opus (if complex reasoning needed)

## When to Use This vs. Simple RAG

Use contextual retrieval when:
- Documents are long (>10 pages)
- Chunks frequently lack standalone meaning
- Retrieval quality is critical to agent accuracy
- You have > 1000 documents

Use simple RAG when:
- Documents are self-contained short pieces
- Speed/cost is the priority
- Retrieval quality is acceptable at baseline
