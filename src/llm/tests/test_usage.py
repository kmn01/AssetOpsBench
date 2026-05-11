"""Tests for CompletionUsage aggregation."""

from types import SimpleNamespace

from llm.usage import CompletionUsage, sum_usage_optional


def test_from_litellm_usage_reads_attributes():
    u = CompletionUsage.from_litellm_usage(
        SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120)
    )
    assert u.prompt_tokens == 100
    assert u.completion_tokens == 20
    assert u.total_tokens == 120


def test_from_litellm_usage_none():
    u = CompletionUsage.from_litellm_usage(None)
    assert u.prompt_tokens is None
    assert u.completion_tokens is None
    assert u.total_tokens is None


def test_add_optional_sums():
    a = CompletionUsage(prompt_tokens=10, completion_tokens=3)
    b = CompletionUsage(prompt_tokens=5, completion_tokens=None)
    c = a + b
    assert c.prompt_tokens == 15
    assert c.completion_tokens == 3


def test_sum_usage_fold():
    total = sum_usage_optional(
        [
            CompletionUsage(1, 2),
            CompletionUsage(3, 4),
        ]
    )
    assert total.prompt_tokens == 4
    assert total.completion_tokens == 6
    assert total.total_tokens == 10


def test_add_sets_total_from_prompt_plus_completion_when_both_known():
    """Provider ``total_tokens`` can disagree with prompt+completion; aggregate must reconcile."""
    a = CompletionUsage(
        prompt_tokens=5976, completion_tokens=200, total_tokens=5778
    )
    b = CompletionUsage(prompt_tokens=0, completion_tokens=55, total_tokens=9999)
    c = a + b
    assert c.prompt_tokens == 5976
    assert c.completion_tokens == 255
    assert c.total_tokens == 5976 + 255


def test_add_sums_provider_totals_when_prompt_or_completion_missing():
    a = CompletionUsage(total_tokens=100)
    b = CompletionUsage(total_tokens=50)
    c = a + b
    assert c.prompt_tokens is None
    assert c.completion_tokens is None
    assert c.total_tokens == 150
