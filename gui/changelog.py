#!/usr/bin/env python3
"""Disenchanted changelog, newest first. Versions follow yyyymmdd.v."""

CHANGELOG = """Disenchanted — Changelog
========================

20261003.1
----------
- Date-based versioning (yyyymmdd.v) shown in the window title and Settings → About.
- Conversation sidebar: all chats saved automatically (timestamped messages),
  resume/double-click, right-click to export as markdown or delete.
- Per-task model selection (Settings → Tasks): separate models for session
  title generation, context compression, and vision fallback.
- Context compression (Settings → Compression): when the conversation reaches a
  user-set % of the model context window, a summarization model compresses
  older turns. Custom compression prompt with a reset-to-default button.
- Live context meter in the top bar (estimated tokens / % of window).
- File attachments: attach documents (text, code, markdown, PDF, HTML...) to
  messages; processed with per-type ingestion to protect the context window.
- SearXNG support (Settings → Search): optional metasearch tool for the LLM,
  user-configurable URL/categories/language/safesearch.
- MCP support (Settings → MCP): connect MCP servers (stdio or HTTP), toggle
  them per chat from the MCP button; tools appear to the model automatically.
- HRR memory (Settings → Attachments & Memory): optional episodic memory with
  associative recall injected into context; full viewer/editor dialog.
- System prompt database (Settings → Prompts): create, edit, reuse named prompts.
- Inline image generation: '/image <prompt>' command powered by dtline
  (Draw Things gRPC), configurable in Settings → Image Gen.
- Update check at launch (once/day) with 'Update and restart' (Settings and
  startup banner) and this changelog page.

Improvements
- Timestamps on every chat bubble; current date/time injected into the model
  context so the model can answer time questions.
- Refactored GUI internals into modules (session persistence, bubbles,
  workers) — same behavior, easier maintenance.
- Updated the bundled ModuLLe library (time/date tools, response cleaner,
  Ollama Cloud provider, decision models).

Earlier
-------
- Screenshot-to-AI: instant screen capture analysis from a KDE shortcut.
- Web research with tool calling (DuckDuckGo search + page fetching).
- Multi-provider AI: Ollama, LM Studio, OpenAI, Gemini, Claude.
"""