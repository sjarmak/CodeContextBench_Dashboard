"""Prompt template system for the unified LLM judge."""

from src.judge.prompts.loader import PromptTemplate, load_template, render

__all__ = [
    "PromptTemplate",
    "load_template",
    "render",
]
