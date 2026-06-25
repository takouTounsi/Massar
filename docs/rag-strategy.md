# RAG Strategy

The MVP ships with 12 synthetic resources, metadata filters and a deterministic local embedding provider. Retrieval combines:

- country match
- diagnosed stage match
- business type
- primary need
- blocker match
- weak score focus

Each returned resource includes `source_url`, `source_chunk_ids` and `synthetic: true`. The ingestion script writes chunk metadata and hash-based embeddings to `data/processed/resource_chunks.json`.
