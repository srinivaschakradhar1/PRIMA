"""LangGraph-style agents for the RAG ingestion and search pipelines.

Each agent is a small, single-responsibility unit that prefers a GPT-4o call
and degrades to a deterministic heuristic when the LLM is unavailable. They are
composed sequentially by the ingestion / search orchestrators (the same graph
described in the technical design's LangGraph section).
"""
