"""Traditional RAG (Retrieval-Augmented Generation) runner for benchmarking comparison.

This runner demonstrates traditional RAG approach:
  1. Retrieve chunks from knowledge base (same as Knowledge Plugin)
  2. Format chunks as LLM prompt
  3. Call LLM to generate answer
  4. Measure performance (latency, tokens, cost)

Usage for benchmarking:
  uv run plan-execute "What are the pump seal inspection procedures?" --rag-mode
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from llm import LLMBackend

from ..models import OrchestratorResult
from ..runner import AgentRunner
from .metrics import PlanExecuteMetrics
from .models import Plan, PlanStep

_log = logging.getLogger(__name__)

_RAG_GENERATION_PROMPT = """\
You are an expert in industrial asset operations and maintenance.

Based on the following knowledge base information:

{context}

Please answer this question comprehensively and in detail:

Question: {question}

Provide a detailed, accurate answer based ONLY on the information provided above. \
If the information doesn't contain the answer, say so clearly. \
Include specific procedures, steps, and details as relevant.
"""


class RAGRunner(AgentRunner):
    """Traditional RAG runner for performance comparison with Knowledge Plugin.

    This runner:
    1. Queries the knowledge plugin to retrieve chunks (same retrieval)
    2. Formats chunks as LLM prompt (RAG approach)
    3. Calls LLM to generate answer (RAG generation step)
    4. Collects metrics for comparison

    Usage::

        from agent.plan_execute.rag_runner import RAGRunner
        from llm import LiteLLMBackend

        runner = RAGRunner(llm=LiteLLMBackend("watsonx/meta-llama/llama-3-3-70b-instruct"))
        result = await runner.run("What are the pump seal inspection procedures?")
        print(result.answer)
    """

    def __init__(
        self,
        llm: LLMBackend,
        server_paths: dict[str, Path | str] | None = None,
    ) -> None:
        super().__init__(llm, server_paths)
        # Don't initialize metrics here - will be created after run() completes
        self._metrics: PlanExecuteMetrics | None = None

    async def run(self, question: str) -> OrchestratorResult:
        """Run traditional RAG for the question.

        Steps:
        1. Initialize knowledge plugin (retrieval setup)
        2. Search for relevant chunks
        3. Format as prompt
        4. Call LLM for generation
        5. Collect metrics
        """
        start_time = time.time()

        try:
            # Step 1: Retrieve chunks using knowledge plugin
            _log.info("RAG: Step 1 - Retrieving chunks from knowledge base")
            retrieval_start = time.time()
            chunks = self._retrieve_chunks(question)
            retrieval_time = time.time() - retrieval_start

            if not chunks:
                metrics = PlanExecuteMetrics(
                    discover_ms=0,
                    plan_ms=0,
                    execute_ms=int(retrieval_time * 1000),
                    summarize_ms=0,
                    e2e_ms=int((time.time() - start_time) * 1000),
                    success=False,
                    plan_steps=0,
                    history_steps=0,
                    tool_calls_attempted=0,
                    tool_calls_succeeded=0,
                    failed_steps=0,
                )
                return OrchestratorResult(
                    question=question,
                    answer="No relevant documents found in knowledge base.",
                    plan=Plan(steps=[], raw="No chunks retrieved"),
                    history=[],
                    metrics=metrics,
                )

            # Step 2: Format chunks as context
            _log.info(f"RAG: Retrieved {len(chunks)} chunks")
            context = self._format_context(chunks)
            context_size = len(context.split())

            # Step 3: Generate with LLM
            _log.info(f"RAG: Step 2 - Calling LLM for generation (context: {context_size} tokens)")
            generation_start = time.time()
            prompt = _RAG_GENERATION_PROMPT.format(context=context, question=question)
            answer, usage = self._llm.generate_with_usage(prompt)
            generation_time = time.time() - generation_start

            total_time = time.time() - start_time

            # Create metrics
            metrics = PlanExecuteMetrics(
                discover_ms=0,
                plan_ms=0,
                execute_ms=int(retrieval_time * 1000),
                summarize_ms=int(generation_time * 1000),
                e2e_ms=int(total_time * 1000),
                success=True,
                plan_steps=2,
                history_steps=2,
                tool_calls_attempted=1,
                tool_calls_succeeded=1,
                failed_steps=0,
                summarize_usage=usage,
            )

            _log.info(f"RAG: Answer generated in {generation_time:.3f}s (total: {total_time:.3f}s)")

            return OrchestratorResult(
                question=question,
                answer=answer,
                plan=Plan(
                    steps=[
                        PlanStep(
                            step_number=1,
                            task="Retrieve knowledge",
                            server="knowledge",
                            tool="search_by_keyword",
                            tool_args={"query": question},
                            dependencies=[],
                            expected_output="Document chunks with context"
                        ),
                        PlanStep(
                            step_number=2,
                            task="Generate answer with LLM",
                            server="llm",
                            tool="generate",
                            tool_args={"prompt": f"Based on: {context_size} tokens context"},
                            dependencies=[1],
                            expected_output="Generated prose answer"
                        )
                    ],
                    raw="RAG mode: retrieve chunks then call LLM for generation"
                ),
                history=[],
                metrics=metrics,
            )

        except Exception as e:
            _log.error(f"RAG runner error: {e}", exc_info=True)
            total_time = time.time() - start_time
            metrics = PlanExecuteMetrics(
                discover_ms=0,
                plan_ms=0,
                execute_ms=0,
                summarize_ms=0,
                e2e_ms=int(total_time * 1000),
                success=False,
                plan_steps=0,
                history_steps=0,
                tool_calls_attempted=0,
                tool_calls_succeeded=0,
                failed_steps=1,
            )
            return OrchestratorResult(
                question=question,
                answer=f"Error: {str(e)}",
                plan=Plan(steps=[], raw=f"Error: {str(e)}"),
                history=[],
                metrics=metrics,
            )

    def _retrieve_chunks(self, question: str) -> list[dict]:
        """Retrieve chunks from knowledge plugin using cross-asset search."""
        try:
            # Import here to avoid circular dependencies
            from servers.knowledge.retriever import search_by_keyword

            _log.debug(f"RAG: Searching for: {question}")

            # Search across all asset types
            results = search_by_keyword(question, top_k=3)  # Use same top-k as Knowledge Plugin for fair comparison

            chunks = []
            for result in results:
                chunks.append({
                    "text": result.get("text", ""),
                    "source": result.get("source", "unknown"),
                    "page": result.get("page", "unknown"),
                    "confidence": result.get("similarity", 0),
                })

            _log.info(f"RAG: Retrieved {len(chunks)} chunks for generation")
            return chunks

        except Exception as e:
            _log.error(f"RAG: Retrieval failed: {e}", exc_info=True)
            return []

    def _format_context(self, chunks: list[dict]) -> str:
        """Format retrieved chunks as context for LLM prompt."""
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            page = chunk.get("page", "?")
            confidence = chunk.get("confidence", 0)
            text = chunk.get("text", "")

            context_parts.append(
                f"[{i}] Source: {source} (Page {page}, {confidence:.0%} confidence)\n{text}"
            )

        return "\n\n".join(context_parts)
