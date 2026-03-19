# Contextual Retrieval Reference

## Why Naive RAG Fails

Standard RAG splits documents into chunks and embeds them. The problem: chunks lose their context. "The revenue increased by 12%" becomes meaningless without knowing which company, which period, which metric.

```
BAD (naive RAG):
  Chunk: "The revenue increased by 12% compared to the previous quarter."
  Problem: Which company? Which quarter? The embedding can't capture this.

GOOD (contextual RAG):
  Chunk: "[From Acme Corp 2024 Q3 earnings report, section: Financial Highlights]
          The revenue increased by 12% compared to the previous quarter."
  Fix: Context added before embedding — now semantically complete.
```

## The Contextual Retrieval Pipeline

```
Document
  -> Split into 500-token chunks (50-token overlap)
  -> For each chunk, generate 50-100 token context with Haiku:
      "This chunk is from [doc title]. It describes [what this chunk covers]
       in the context of [broader document topic]."
  -> Store: context + chunk (combined) in both:
      - Vector index (semantic search — catches meaning)
      - BM25 index (keyword search — catches exact terms)

At query time:
  -> Run hybrid retrieval (top-20 from each index)
  -> Deduplicate + merge
  -> Rerank to top-5
  -> Use top-5 as context for the LLM
```

## Implementation

```python
import anthropic

client = anthropic.Anthropic()

def split_document(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by token estimate."""
    words = text.split()
    # Rough approximation: 1 token ~= 0.75 words
    words_per_chunk = int(chunk_size * 0.75)
    overlap_words = int(overlap * 0.75)

    chunks = []
    start = 0
    while start < len(words):
        end = start + words_per_chunk
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap_words  # Overlap with previous chunk
    return chunks


def enrich_chunk(chunk: str, doc_title: str, doc_summary: str) -> str:
    """Add context to a chunk before indexing. Use Haiku for cost efficiency."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{
            "role": "user",
            "content": f"""Document: {doc_title}
Summary: {doc_summary[:200]}

Chunk: {chunk}

Write 2-3 sentences: what is this chunk about, and how does it fit in the broader document? Be specific — include key entities and relationships."""
        }]
    )
    context = response.content[0].text
    return f"{context}\n\n{chunk}"


def build_index(documents: list[dict], vector_index, bm25_index):
    """Index all documents with contextual enrichment."""
    for doc in documents:
        chunks = split_document(doc["text"])
        for i, chunk in enumerate(chunks):
            enriched = enrich_chunk(chunk, doc["title"], doc.get("summary", ""))
            chunk_id = f"{doc['id']}_chunk_{i}"
            vector_index.add(enriched, metadata={"chunk_id": chunk_id, "doc_id": doc["id"]})
            bm25_index.add(enriched, metadata={"chunk_id": chunk_id, "doc_id": doc["id"]})


def retrieve(query: str, vector_index, bm25_index, reranker, top_k: int = 5) -> list[dict]:
    """Hybrid retrieval with reranking."""
    # Get candidates from both indexes
    vector_results = vector_index.search(query, k=20)
    bm25_results = bm25_index.search(query, k=20)

    # Merge and deduplicate
    seen = set()
    combined = []
    for result in vector_results + bm25_results:
        if result["chunk_id"] not in seen:
            seen.add(result["chunk_id"])
            combined.append(result)

    # Rerank for final selection
    reranked = reranker.rerank(combined, query)
    return reranked[:top_k]
```

## Failure Rate Reduction

Each technique compounds on the previous:

| Method | Failure Rate | Reduction vs Baseline |
|--------|:-----------:|:---------------------:|
| Baseline RAG | 5.7% | -- |
| + Contextual embeddings | 3.7% | -35% |
| + BM25 hybrid search | 2.9% | -49% |
| + Reranking | 1.9% | **-67%** |

## Cost Optimization

### Prompt Caching for Context Generation

The expensive part of contextual retrieval is generating context for every chunk. Use prompt caching to amortize the cost:

```python
# The document corpus goes in the system prompt with cache control
# Subsequent chunk enrichment calls hit the cache
# Cost: ~$1.02/M tokens (cached) vs $15/M tokens (uncached)

# In practice: for a 10,000-document corpus with ~50 chunks each,
# contextual enrichment costs ~$20-50 total with caching vs ~$200-500 without
```

### Model Selection by Task

| Task | Recommended Model | Why |
|------|------------------|-----|
| Context generation (enrichment) | Claude Haiku | Cheap, fast, mechanical task |
| Reranking | Sonnet or dedicated reranker | Quality matters for final selection |
| Final answer generation | Sonnet or Opus | Depends on reasoning complexity |

## When to Use Contextual RAG vs Simple RAG

### Use Contextual RAG When:

- Documents are long (> 10 pages) — chunks frequently lack standalone meaning
- Domain is technical — terms are ambiguous without context
- Retrieval quality is critical — wrong context = wrong agent decisions
- You have > 1,000 documents — scale justifies setup cost
- Documents have internal structure — sections reference earlier sections

### Use Simple RAG When:

- Documents are self-contained short pieces (FAQ entries, product descriptions)
- Speed is the top priority — enrichment adds indexing time
- Document corpus is small (< 100 docs) — just load them all into context
- Chunks are naturally complete — each paragraph stands alone

### Skip RAG Entirely When:

- Corpus fits in context window (< 100K tokens) — just put it in the prompt
- Information changes too frequently — re-indexing cost is too high
- Exact retrieval is required — use structured search (SQL, Elasticsearch)

## Integrating RAG with Agents

### RAG as a Tool

```python
rag_tool = {
    "name": "search_knowledge_base",
    "description": "Search the company knowledge base for information. Use when the user asks about product features, policies, or technical specifications. Returns the 5 most relevant passages with source documents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for — be specific"
            },
            "filter_category": {
                "type": "string",
                "description": "Optional category filter",
                "enum": ["product", "policy", "technical", "all"]
            }
        },
        "required": ["query"]
    }
}
```

### Common Mistakes with RAG in Agents

| Mistake | Problem | Fix |
|---------|---------|-----|
| Agent retrieves too much | Context fills up, quality drops | Limit to top-5 results, keep total under 2K tokens |
| No source attribution | Agent hallucinates beyond retrieved context | Return source metadata, prompt agent to cite |
| Stale index | Agent gives outdated information | Add "last updated" to metadata, warn about freshness |
| Retrieval on every turn | Unnecessary API calls, adds latency | Only retrieve when the agent doesn't already have the answer in context |
| Dumping raw chunks | Agent confused by fragmented text | Use enriched chunks with context |

## Evaluation for RAG Systems

```python
def eval_rag_quality(questions: list[dict], retrieve_fn, answer_fn) -> dict:
    """Evaluate RAG system on a set of questions with known answers."""
    results = {"retrieval_hits": 0, "answer_correct": 0, "total": len(questions)}

    for q in questions:
        # Check retrieval quality
        retrieved = retrieve_fn(q["question"])
        relevant_found = any(
            q["expected_source"] in r.get("doc_id", "")
            for r in retrieved
        )
        results["retrieval_hits"] += int(relevant_found)

        # Check answer quality
        answer = answer_fn(q["question"], retrieved)
        correct = q["expected_answer"].lower() in answer.lower()
        results["answer_correct"] += int(correct)

    results["retrieval_accuracy"] = results["retrieval_hits"] / results["total"]
    results["answer_accuracy"] = results["answer_correct"] / results["total"]
    return results
```
