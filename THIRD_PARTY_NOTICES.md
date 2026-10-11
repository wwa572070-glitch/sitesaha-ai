# Third-Party Notices

## RAG-Construction-Assistant

- Repository: https://github.com/priscilla254/RAG-Construction-Assistant
- Copyright: Copyright (c) 2026 Priscilla Wambui
- License: MIT
- Local reference copy: `third_party/github/RAG-Construction-Assistant/`

The SiteSaha AI hybrid retrieval design was adapted from this project's
weighted reciprocal rank fusion and per-source result cap. The original uses
BM25, Chroma and a hosted model; SiteSaha replaces those components with
SQLite FTS5, a deterministic local sparse-vector index, and an optional local
OpenAI-compatible model endpoint.

The full MIT license is retained in the local reference copy and in
`licenses/RAG-Construction-Assistant-MIT.txt`.
