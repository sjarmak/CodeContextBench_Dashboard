"""
Enhanced LLM Judge Module

Reusable LLM-based evaluation for agent runs following best practices:
- Reference-guided evaluation with oracle/ground truth data
- Simplified 3-point scoring (pass/partial/fail)
- Multi-judge voting for consistency
- Step decomposition for complex evaluations
- MCP tool effectiveness evaluation

Based on research from:
- Monte Carlo: LLM-As-Judge Best Practices
- arXiv Survey on LLM-as-a-Judge (2411.15594)
- Evidently AI: LLM-as-a-Judge Guide
"""

import json
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import anthropic
except ImportError:
    anthropic = None

from .evaluation_schema import JudgeAssessment

# =============================================================================
# Enhanced Input Schema
# =============================================================================


@dataclass
class EnhancedJudgeInput:
    """Enhanced input for LLM judge evaluation with oracle data support."""

    # Core fields
    task_id: str
    task_description: str
    code_changes: str = ""
    tool_calls: str = ""
    reward: float = 0.0
    trajectory: str = ""

    # Oracle/Ground Truth (from load_locobench_oracle)
    oracle_ground_truth: Optional[str] = None
    oracle_expected_approach: Optional[str] = None
    oracle_evaluation_criteria: Optional[List[str]] = None
    oracle_context_files: Optional[List[str]] = None

    # MCP Tool Analysis (from analyze_mcp_tool_usage)
    mcp_tools_used: Optional[List[Dict[str, Any]]] = None
    mcp_effectiveness_score: Optional[float] = None
    mcp_recommendations: Optional[List[str]] = None

    # Task metadata
    task_category: Optional[str] = None  # "Code Modification" vs "Analysis"
    difficulty: Optional[str] = None
    repository: Optional[str] = None

    def has_oracle_data(self) -> bool:
        """Check if oracle data is available."""
        return bool(self.oracle_ground_truth or self.oracle_evaluation_criteria)

    def has_mcp_data(self) -> bool:
        """Check if MCP tool data is available."""
        return bool(self.mcp_tools_used)


@dataclass
class EnhancedJudgeAssessment:
    """Enhanced assessment with voting and oracle alignment."""

    dimension: str
    score: float  # 0.0 (fail), 0.5 (partial), 1.0 (pass)
    score_label: str  # "pass", "partial", "fail"
    reasoning: str
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    judge_model: str = ""

    # Oracle alignment (when oracle data available)
    oracle_alignment: Optional[str] = None  # "full", "partial", "none"
    criteria_met: Optional[List[Dict[str, Any]]] = None  # Per-criterion results

    # Voting metadata (when multi-round voting used)
    vote_distribution: Optional[Dict[str, int]] = None
    confidence: Optional[float] = None
    num_rounds: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "score": self.score,
            "score_label": self.score_label,
            "reasoning": self.reasoning,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "judge_model": self.judge_model,
            "oracle_alignment": self.oracle_alignment,
            "criteria_met": self.criteria_met,
            "vote_distribution": self.vote_distribution,
            "confidence": self.confidence,
            "num_rounds": self.num_rounds,
        }

    def to_legacy_assessment(self) -> JudgeAssessment:
        """Convert to legacy JudgeAssessment for backward compatibility."""
        # Map 0-1 score to 0-4 scale for legacy compatibility
        legacy_score = self.score * 4.0
        return JudgeAssessment(
            dimension=self.dimension,
            score=legacy_score,
            reasoning=self.reasoning,
            strengths=self.strengths,
            weaknesses=self.weaknesses,
            judge_model=self.judge_model,
        )


# =============================================================================
# Scoring System
# =============================================================================

# 3-point categorical scoring (more reliable than 0-4 scales)
SCORE_PASS = 1.0
SCORE_PARTIAL = 0.5
SCORE_FAIL = 0.0

SCORE_LABELS = {
    SCORE_PASS: "pass",
    SCORE_PARTIAL: "partial",
    SCORE_FAIL: "fail",
}


def normalize_score(raw_score: str) -> tuple[float, str]:
    """Normalize string score to numeric value and label."""
    raw_lower = raw_score.lower().strip()
    if raw_lower in ("pass", "full", "effective", "1", "1.0"):
        return SCORE_PASS, "pass"
    elif raw_lower in ("partial", "partially", "partially_effective", "0.5"):
        return SCORE_PARTIAL, "partial"
    else:
        return SCORE_FAIL, "fail"


# =============================================================================
# Oracle-Guided Prompts (Best Practice: Reference-Guided Evaluation)
# =============================================================================

ORACLE_CORRECTNESS_PROMPT = """You are an expert evaluator comparing an AI agent's solution against a known correct answer.

## Task Description
{task_description}

## Expected Answer (Ground Truth)
{oracle_ground_truth}

## Expected Approach
{oracle_expected_approach}

## Evaluation Criteria
{oracle_criteria_formatted}

## Agent's Solution
{code_changes}

## Test Result
Reward: {reward} (1.0 = tests passed, 0.0 = tests failed)

---

## Step-by-Step Evaluation

First, analyze how well the agent's solution aligns with the expected answer:

1. **Key Concepts**: Does the solution identify the same key concepts as the ground truth?
2. **Approach**: Does the solution follow a similar approach to the expected approach?
3. **Completeness**: Does the solution cover all the evaluation criteria?

Then provide your final assessment.

## Scoring Guide
- **pass**: Solution correctly captures the key elements of the ground truth
- **partial**: Solution captures some elements but misses important aspects
- **fail**: Solution does not align with the ground truth

Respond with JSON only:
{{
    "criteria_analysis": [
        {{"criterion": "<criterion text>", "met": true, "evidence": "<quote from solution>"}}
    ],
    "alignment_score": "pass" | "partial" | "fail",
    "reasoning": "<2-3 sentences explaining the alignment>",
    "key_matches": ["<element that matches ground truth>"],
    "key_differences": ["<element that differs from ground truth>"]
}}
"""

ORACLE_COMPLETENESS_PROMPT = """You are evaluating how completely an AI agent addressed a task, using known evaluation criteria.

## Task Description
{task_description}

## Evaluation Criteria (Agent should address all)
{oracle_criteria_formatted}

## Agent's Solution
{code_changes}

---

## Evaluation

Check each criterion and determine if the agent's solution addresses it.

## Scoring Guide
- **pass**: All or nearly all criteria are addressed (>80%)
- **partial**: Some criteria are addressed (40-80%)
- **fail**: Few or no criteria are addressed (<40%)

Respond with JSON only:
{{
    "criteria_results": [
        {{"criterion": "<criterion text>", "addressed": true, "evidence": "<quote or explanation>"}}
    ],
    "addressed_count": <number>,
    "total_count": <number>,
    "coverage_percent": <0-100>,
    "score": "pass" | "partial" | "fail",
    "reasoning": "<2-3 sentences explaining coverage>"
}}
"""

MCP_EFFECTIVENESS_PROMPT = """You are evaluating an AI agent's use of MCP (Model Context Protocol) and Sourcegraph tools.

## Available MCP Tools
- mcp__sourcegraph__sg_deepsearch: Semantic code search for understanding architecture
- mcp__sourcegraph__sg_keyword_search: Grep-style keyword search
- mcp__sourcegraph__sg_read_file: Read specific file contents

## Task Description
{task_description}

## Files Agent Should Have Found
{oracle_context_files}

## Agent's Tool Usage
{tool_usage_formatted}

## MCP Tools Used
{mcp_tools_formatted}

---

## Evaluation Criteria

1. **Search Strategy**: Did the agent use semantic search (deepsearch) for architectural questions?
2. **File Discovery**: Did the agent find the relevant files listed above?
3. **Efficiency**: Did the agent avoid excessive redundant searches?
4. **Tool Selection**: Did the agent use the right tool for each search type?

## Scoring Guide
- **effective**: Good use of MCP tools, found relevant files, efficient searches
- **partially_effective**: Some MCP tool use, found some files, some inefficiency
- **ineffective**: No/poor MCP tool use, missed key files, or excessive redundancy

Respond with JSON only:
{{
    "used_deepsearch": true | false,
    "used_keyword_search": true | false,
    "files_found": ["<file1>", "<file2>"],
    "files_missed": ["<file1>", "<file2>"],
    "redundant_search_count": <number>,
    "strategy_assessment": "good" | "adequate" | "poor",
    "score": "effective" | "partially_effective" | "ineffective",
    "reasoning": "<2-3 sentences>",
    "recommendations": ["<suggestion 1>", "<suggestion 2>"]
}}
"""

# =============================================================================
# Fallback Prompts (when no oracle data available)
# =============================================================================

CORRECTNESS_PROMPT_SIMPLE = """You are evaluating whether an AI agent's solution correctly addresses a coding task.

## Task Description
{task_description}

## Agent's Solution (Code Changes)
{code_changes}

## Test Result
Reward: {reward} (1.0 = tests passed, 0.0 = tests failed)

Note: Test results are informative but not definitive. Focus on solution quality.

## Scoring Guide
- **pass**: Solution correctly addresses the core issue
- **partial**: Solution addresses part of the issue but has gaps
- **fail**: Solution does not address the issue or is incorrect

Respond with JSON only:
{{
    "score": "pass" | "partial" | "fail",
    "reasoning": "<2-3 sentences>",
    "strengths": ["<strength 1>"],
    "weaknesses": ["<weakness 1>"]
}}
"""

RETRIEVAL_PROMPT_SIMPLE = """You are evaluating an AI agent's code search and retrieval strategy.

## Task Description
{task_description}

## Agent's Tool Usage
{tool_calls}

## Scoring Guide
- **pass**: Agent used effective search strategy and found relevant code
- **partial**: Agent found some relevant code but missed key areas
- **fail**: Agent's search strategy was poor or found wrong code

Respond with JSON only:
{{
    "score": "pass" | "partial" | "fail",
    "reasoning": "<2-3 sentences>",
    "strengths": ["<strength 1>"],
    "weaknesses": ["<weakness 1>"]
}}
"""

CODE_QUALITY_PROMPT_SIMPLE = """You are evaluating the quality of an AI agent's code solution.

## Task Description
{task_description}

## Agent's Code Changes
{code_changes}

## Scoring Guide
- **pass**: Code is clean, idiomatic, and well-structured
- **partial**: Code works but has quality issues
- **fail**: Code has significant quality problems

Respond with JSON only:
{{
    "score": "pass" | "partial" | "fail",
    "reasoning": "<2-3 sentences>",
    "strengths": ["<strength 1>"],
    "weaknesses": ["<weakness 1>"]
}}
"""


# =============================================================================
# Enhanced LLM Judge Class
# =============================================================================


class EnhancedLLMJudge:
    """
    Enhanced LLM Judge with oracle support and best practices.

    Features:
    - Reference-guided evaluation when oracle data available
    - Simplified 3-point scoring (pass/partial/fail)
    - Multi-round voting for consistency
    - MCP tool effectiveness evaluation
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: Optional[str] = None,
        enable_voting: bool = True,
        voting_rounds: int = 3,
    ):
        """
        Initialize enhanced LLM judge.

        Args:
            model: Model name for judging
            api_key: Anthropic API key
            enable_voting: Whether to use multi-round voting
            voting_rounds: Number of voting rounds (default 3)
        """
        if anthropic is None:
            raise ImportError("anthropic package required. Run: pip install anthropic")

        self.model = model
        self.enable_voting = enable_voting
        self.voting_rounds = voting_rounds

        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.Anthropic(api_key=api_key)

    def evaluate(
        self,
        judge_input: EnhancedJudgeInput,
        dimension: str,
    ) -> EnhancedJudgeAssessment:
        """
        Evaluate a single dimension with optional voting.

        Args:
            judge_input: Enhanced input with oracle data
            dimension: Dimension to evaluate

        Returns:
            EnhancedJudgeAssessment with score and metadata
        """
        if self.enable_voting:
            return self._evaluate_with_voting(judge_input, dimension)
        else:
            return self._single_evaluation(judge_input, dimension)

    def evaluate_all(
        self,
        judge_input: EnhancedJudgeInput,
        dimensions: Optional[List[str]] = None,
    ) -> List[EnhancedJudgeAssessment]:
        """
        Evaluate all specified dimensions.

        Args:
            judge_input: Enhanced input with oracle data
            dimensions: List of dimensions to evaluate (default: auto-select)

        Returns:
            List of EnhancedJudgeAssessment objects
        """
        if dimensions is None:
            # Auto-select dimensions based on available data
            dimensions = ["correctness", "completeness"]
            if judge_input.tool_calls:
                dimensions.append("retrieval")
            if judge_input.has_mcp_data():
                dimensions.append("mcp_effectiveness")
            if judge_input.code_changes:
                dimensions.append("code_quality")

        return [self.evaluate(judge_input, dim) for dim in dimensions]

    def _evaluate_with_voting(
        self,
        judge_input: EnhancedJudgeInput,
        dimension: str,
    ) -> EnhancedJudgeAssessment:
        """Run evaluation multiple times and take majority vote."""
        assessments = []
        for _ in range(self.voting_rounds):
            assessment = self._single_evaluation(judge_input, dimension)
            assessments.append(assessment)

        # Majority vote on score
        scores = [a.score for a in assessments]
        score_counter = Counter(scores)
        final_score = score_counter.most_common(1)[0][0]
        final_label = SCORE_LABELS.get(final_score, "fail")

        # Combine reasoning from all rounds
        all_reasoning = [a.reasoning for a in assessments]
        combined_reasoning = self._merge_reasoning(all_reasoning)

        # Aggregate strengths and weaknesses
        all_strengths = []
        all_weaknesses = []
        for a in assessments:
            all_strengths.extend(a.strengths)
            all_weaknesses.extend(a.weaknesses)

        # Deduplicate
        unique_strengths = list(dict.fromkeys(all_strengths))[:5]
        unique_weaknesses = list(dict.fromkeys(all_weaknesses))[:5]

        # Use oracle data from first assessment
        first = assessments[0]

        return EnhancedJudgeAssessment(
            dimension=dimension,
            score=final_score,
            score_label=final_label,
            reasoning=combined_reasoning,
            strengths=unique_strengths,
            weaknesses=unique_weaknesses,
            judge_model=self.model,
            oracle_alignment=first.oracle_alignment,
            criteria_met=first.criteria_met,
            vote_distribution=dict(score_counter),
            confidence=score_counter.most_common(1)[0][1] / len(scores),
            num_rounds=self.voting_rounds,
        )

    def _merge_reasoning(self, reasoning_list: List[str]) -> str:
        """Merge reasoning from multiple rounds."""
        if len(reasoning_list) == 1:
            return reasoning_list[0]

        # Find the most common themes
        unique_reasonings = list(dict.fromkeys(reasoning_list))
        if len(unique_reasonings) == 1:
            return unique_reasonings[0]

        # Return the longest reasoning (usually most detailed)
        return max(unique_reasonings, key=len)

    def _single_evaluation(
        self,
        judge_input: EnhancedJudgeInput,
        dimension: str,
    ) -> EnhancedJudgeAssessment:
        """Perform a single evaluation for a dimension."""

        if dimension == "correctness":
            return self._evaluate_correctness(judge_input)
        elif dimension == "completeness":
            return self._evaluate_completeness(judge_input)
        elif dimension == "retrieval":
            return self._evaluate_retrieval(judge_input)
        elif dimension == "mcp_effectiveness":
            return self._evaluate_mcp_effectiveness(judge_input)
        elif dimension == "code_quality":
            return self._evaluate_code_quality(judge_input)
        else:
            raise ValueError(f"Unknown dimension: {dimension}")

    def _evaluate_correctness(
        self,
        judge_input: EnhancedJudgeInput,
    ) -> EnhancedJudgeAssessment:
        """Evaluate correctness with oracle data if available."""

        if judge_input.has_oracle_data():
            # Use oracle-guided evaluation
            prompt = ORACLE_CORRECTNESS_PROMPT.format(
                task_description=judge_input.task_description[:2000],
                oracle_ground_truth=judge_input.oracle_ground_truth or "Not provided",
                oracle_expected_approach=judge_input.oracle_expected_approach
                or "Not provided",
                oracle_criteria_formatted=self._format_criteria(
                    judge_input.oracle_evaluation_criteria
                ),
                code_changes=judge_input.code_changes[
                    :20000
                ],  # Increased for full analysis
                reward=judge_input.reward,
            )
        else:
            # Use simple evaluation
            prompt = CORRECTNESS_PROMPT_SIMPLE.format(
                task_description=judge_input.task_description[:2000],
                code_changes=judge_input.code_changes[
                    :20000
                ],  # Increased for full analysis
                reward=judge_input.reward,
            )

        result = self._call_llm(prompt)

        score_str = result.get("alignment_score") or result.get("score", "fail")
        score, label = normalize_score(score_str)

        return EnhancedJudgeAssessment(
            dimension="correctness",
            score=score,
            score_label=label,
            reasoning=result.get("reasoning", "Evaluation failed"),
            strengths=result.get("key_matches", result.get("strengths", [])),
            weaknesses=result.get("key_differences", result.get("weaknesses", [])),
            judge_model=self.model,
            oracle_alignment=result.get("alignment_score"),
            criteria_met=result.get("criteria_analysis"),
        )

    def _evaluate_completeness(
        self,
        judge_input: EnhancedJudgeInput,
    ) -> EnhancedJudgeAssessment:
        """Evaluate completeness with oracle criteria if available."""

        if judge_input.oracle_evaluation_criteria:
            prompt = ORACLE_COMPLETENESS_PROMPT.format(
                task_description=judge_input.task_description[:2000],
                oracle_criteria_formatted=self._format_criteria(
                    judge_input.oracle_evaluation_criteria
                ),
                code_changes=judge_input.code_changes[:20000],
            )
        else:
            # Fallback to simple correctness as proxy for completeness
            prompt = CORRECTNESS_PROMPT_SIMPLE.format(
                task_description=judge_input.task_description[:2000],
                code_changes=judge_input.code_changes[:20000],
                reward=judge_input.reward,
            )

        result = self._call_llm(prompt)

        score_str = result.get("score", "fail")
        score, label = normalize_score(score_str)

        criteria_results = result.get("criteria_results")

        return EnhancedJudgeAssessment(
            dimension="completeness",
            score=score,
            score_label=label,
            reasoning=result.get("reasoning", "Evaluation failed"),
            strengths=[f"{result.get('coverage_percent', 0)}% coverage"]
            if "coverage_percent" in result
            else result.get("strengths", []),
            weaknesses=result.get("weaknesses", []),
            judge_model=self.model,
            criteria_met=criteria_results,
        )

    def _evaluate_retrieval(
        self,
        judge_input: EnhancedJudgeInput,
    ) -> EnhancedJudgeAssessment:
        """Evaluate retrieval/search strategy."""

        prompt = RETRIEVAL_PROMPT_SIMPLE.format(
            task_description=judge_input.task_description[:2000],
            tool_calls=judge_input.tool_calls[:5000],
        )

        result = self._call_llm(prompt)

        score_str = result.get("score", "fail")
        score, label = normalize_score(score_str)

        return EnhancedJudgeAssessment(
            dimension="retrieval",
            score=score,
            score_label=label,
            reasoning=result.get("reasoning", "Evaluation failed"),
            strengths=result.get("strengths", []),
            weaknesses=result.get("weaknesses", []),
            judge_model=self.model,
        )

    def _evaluate_mcp_effectiveness(
        self,
        judge_input: EnhancedJudgeInput,
    ) -> EnhancedJudgeAssessment:
        """Evaluate MCP/Sourcegraph tool effectiveness."""

        prompt = MCP_EFFECTIVENESS_PROMPT.format(
            task_description=judge_input.task_description[:2000],
            oracle_context_files=self._format_file_list(
                judge_input.oracle_context_files
            ),
            tool_usage_formatted=judge_input.tool_calls[:3000],
            mcp_tools_formatted=self._format_mcp_tools(judge_input.mcp_tools_used),
        )

        result = self._call_llm(prompt)

        score_str = result.get("score", "ineffective")
        score, label = normalize_score(score_str)

        recommendations = result.get("recommendations", [])
        if judge_input.mcp_recommendations:
            recommendations.extend(judge_input.mcp_recommendations)

        return EnhancedJudgeAssessment(
            dimension="mcp_effectiveness",
            score=score,
            score_label=label,
            reasoning=result.get("reasoning", "Evaluation failed"),
            strengths=[
                f"Strategy: {result.get('strategy_assessment', 'unknown')}",
                f"Found: {len(result.get('files_found', []))} files",
            ],
            weaknesses=[
                f"Missed: {len(result.get('files_missed', []))} files",
                *recommendations[:3],
            ],
            judge_model=self.model,
        )

    def _evaluate_code_quality(
        self,
        judge_input: EnhancedJudgeInput,
    ) -> EnhancedJudgeAssessment:
        """Evaluate code quality."""

        prompt = CODE_QUALITY_PROMPT_SIMPLE.format(
            task_description=judge_input.task_description[:2000],
            code_changes=judge_input.code_changes[:5000],
        )

        result = self._call_llm(prompt)

        score_str = result.get("score", "fail")
        score, label = normalize_score(score_str)

        return EnhancedJudgeAssessment(
            dimension="code_quality",
            score=score,
            score_label=label,
            reasoning=result.get("reasoning", "Evaluation failed"),
            strengths=result.get("strengths", []),
            weaknesses=result.get("weaknesses", []),
            judge_model=self.model,
        )

    def _format_criteria(self, criteria: Optional[List[str]]) -> str:
        """Format evaluation criteria as numbered list."""
        if not criteria:
            return "No specific criteria provided"

        lines = []
        for i, criterion in enumerate(criteria[:10], 1):
            lines.append(f"{i}. {criterion}")
        return "\n".join(lines)

    def _format_file_list(self, files: Optional[List[str]]) -> str:
        """Format file list for prompt."""
        if not files:
            return "No specific files listed"

        return "\n".join(f"- {f}" for f in files[:20])

    def _format_mcp_tools(self, tools: Optional[List[Dict[str, Any]]]) -> str:
        """Format MCP tool usage for prompt."""
        if not tools:
            return "No MCP tools used"

        lines = []
        for tool in tools[:10]:
            name = tool.get("tool", "unknown")
            count = tool.get("count", 0)
            lines.append(f"- {name}: {count} calls")
        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,  # Increased for detailed reasoning
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text

            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            # Try to parse JSON
            try:
                return json.loads(text.strip())
            except json.JSONDecodeError as je:
                # If JSON parsing fails, try to extract partial JSON
                # This can happen if the response is truncated
                import re

                # Try to find a complete JSON object
                json_match = re.search(
                    r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL
                )
                if json_match:
                    try:
                        return json.loads(json_match.group(0))
                    except:
                        pass
                # Return error with truncated response for debugging
                return {
                    "score": "fail",
                    "reasoning": f"JSON parsing failed: {str(je)}. Response preview: {text[:200]}...",
                    "strengths": [],
                    "weaknesses": ["Evaluation error - malformed JSON response"],
                }
        except Exception as e:
            return {
                "score": "fail",
                "reasoning": f"Evaluation failed: {str(e)}",
                "strengths": [],
                "weaknesses": ["Evaluation error"],
            }


# =============================================================================
# Legacy LLMJudge Class (Backward Compatibility)
# =============================================================================


class LLMJudge:
    """
    Legacy LLM-based judge for agent evaluation.

    Maintained for backward compatibility. New code should use EnhancedLLMJudge.
    """

    def __init__(
        self, model: str = "claude-haiku-4-5-20251001", api_key: Optional[str] = None
    ):
        if anthropic is None:
            raise ImportError("anthropic package required. Run: pip install anthropic")

        self.model = model
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.Anthropic(api_key=api_key)
        self._enhanced_judge = EnhancedLLMJudge(
            model=model, api_key=api_key, enable_voting=False
        )

    def evaluate_retrieval(
        self, task_description: str, tool_calls: str
    ) -> JudgeAssessment:
        """Evaluate retrieval quality (legacy interface)."""
        judge_input = EnhancedJudgeInput(
            task_id="legacy",
            task_description=task_description,
            tool_calls=tool_calls,
        )
        result = self._enhanced_judge._evaluate_retrieval(judge_input)
        return result.to_legacy_assessment()

    def evaluate_code(
        self, task_description: str, code_changes: str, reward: float
    ) -> JudgeAssessment:
        """Evaluate code quality (legacy interface)."""
        judge_input = EnhancedJudgeInput(
            task_id="legacy",
            task_description=task_description,
            code_changes=code_changes,
            reward=reward,
        )
        result = self._enhanced_judge._evaluate_code_quality(judge_input)
        return result.to_legacy_assessment()

    def evaluate_correctness(
        self, task_description: str, code_changes: str, trajectory: str, reward: float
    ) -> JudgeAssessment:
        """Evaluate correctness (legacy interface)."""
        judge_input = EnhancedJudgeInput(
            task_id="legacy",
            task_description=task_description,
            code_changes=code_changes,
            trajectory=trajectory,
            reward=reward,
        )
        result = self._enhanced_judge._evaluate_correctness(judge_input)
        return result.to_legacy_assessment()

    def evaluate_completeness(
        self, task_description: str, code_changes: str, trajectory: str, reward: float
    ) -> JudgeAssessment:
        """Evaluate completeness (legacy interface)."""
        judge_input = EnhancedJudgeInput(
            task_id="legacy",
            task_description=task_description,
            code_changes=code_changes,
            trajectory=trajectory,
            reward=reward,
        )
        result = self._enhanced_judge._evaluate_completeness(judge_input)
        return result.to_legacy_assessment()


# =============================================================================
# Helper Functions
# =============================================================================


def extract_tool_calls_from_trajectory(trajectory: Dict) -> str:
    """Extract search/retrieval tool calls from trajectory for judge evaluation."""
    tool_calls = []

    for step in trajectory.get("steps", []):
        extra = step.get("extra", {})
        tool_name = extra.get("tool_use_name", "")

        if tool_name:
            if any(
                x in tool_name.lower()
                for x in ["search", "grep", "find", "read", "mcp__", "sg_", "glob"]
            ):
                raw_args = extra.get("raw_arguments", {})
                tool_calls.append({"tool": tool_name, "input": raw_args})

    # Also check old format
    for step in trajectory.get("steps", []):
        if step.get("source") != "agent":
            continue

        content = step.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name", "")
                    if any(
                        x in name.lower()
                        for x in ["search", "grep", "find", "read", "mcp__", "sg_"]
                    ):
                        input_data = item.get("input", {})
                        tool_calls.append({"tool": name, "input": input_data})

    if not tool_calls:
        return "No search/retrieval tool calls found"

    lines = []
    for i, call in enumerate(tool_calls[:30], 1):
        lines.append(f"{i}. {call['tool']}")
        if isinstance(call["input"], dict):
            for k, v in list(call["input"].items())[:3]:
                v_str = str(v)[:200]
                lines.append(f"   {k}: {v_str}")

    if len(tool_calls) > 30:
        lines.append(f"... and {len(tool_calls) - 30} more calls")

    return "\n".join(lines)


def extract_code_changes_from_trajectory(trajectory: Dict) -> str:
    """Extract code edit operations from trajectory for judge evaluation."""
    changes = []

    for step in trajectory.get("steps", []):
        extra = step.get("extra", {})
        tool_name = extra.get("tool_use_name", "")

        if tool_name and any(
            x in tool_name.lower() for x in ["edit", "write", "create", "replace"]
        ):
            raw_args = extra.get("raw_arguments", {})
            file_path = raw_args.get("file_path", raw_args.get("path", "unknown"))

            if "edit" in tool_name.lower():
                old_str = raw_args.get("old_string", "")
                new_str = raw_args.get("new_string", "")
                changes.append(
                    {
                        "type": "edit",
                        "file": file_path,
                        "old": old_str,
                        "new": new_str,
                    }
                )
            elif "write" in tool_name.lower():
                content = raw_args.get("content", "")
                changes.append(
                    {
                        "type": "write",
                        "file": file_path,
                        "content": content,
                    }
                )

    # Also check old format
    for step in trajectory.get("steps", []):
        if step.get("source") != "agent":
            continue

        content = step.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name", "")
                    input_data = item.get("input", {})

                    if "edit" in name.lower():
                        old_str = input_data.get("old_string", "")
                        new_str = input_data.get("new_string", "")
                        file_path = input_data.get(
                            "file_path", input_data.get("path", "unknown")
                        )
                        changes.append(
                            {
                                "type": "edit",
                                "file": file_path,
                                "old": old_str,
                                "new": new_str,
                            }
                        )
                    elif "write" in name.lower() or "create" in name.lower():
                        content_str = input_data.get("content", "")
                        file_path = input_data.get(
                            "file_path", input_data.get("path", "unknown")
                        )
                        changes.append(
                            {
                                "type": "write",
                                "file": file_path,
                                "content": content_str,
                            }
                        )

    if not changes:
        return "No code changes found"

    lines = []
    for i, change in enumerate(changes[:20], 1):
        if change["type"] == "edit":
            lines.append(f"\n{i}. EDIT: {change['file']}")
            lines.append("=" * 60)
            lines.append("OLD:")
            lines.append(
                change["old"][:2000] if len(change["old"]) > 2000 else change["old"]
            )
            lines.append("\nNEW:")
            lines.append(
                change["new"][:2000] if len(change["new"]) > 2000 else change["new"]
            )
            lines.append("=" * 60)
        elif change["type"] == "write":
            lines.append(f"\n{i}. WRITE: {change['file']}")
            lines.append("=" * 60)
            content = (
                change["content"][:2000]
                if len(change["content"]) > 2000
                else change["content"]
            )
            lines.append(content)
            lines.append("=" * 60)

    if len(changes) > 20:
        lines.append(f"\n... and {len(changes) - 20} more changes")

    return "\n".join(lines)


def load_task_description(task_path: Path) -> str:
    """Load task description from common instruction files."""
    for filename in [
        "instruction.md",
        "TASK.md",
        "prompt.md",
        "task.md",
        "README.md",
    ]:
        task_file = task_path / filename
        if task_file.exists():
            return task_file.read_text()

    # Try task.toml
    toml_file = task_path / "task.toml"
    if toml_file.exists():
        return toml_file.read_text()

    return "Task description not found"


def create_enhanced_input_from_oracle(
    task_id: str,
    task_description: str,
    code_changes: str,
    tool_calls: str,
    reward: float,
    oracle_data: Dict[str, Any],
    mcp_analysis: Optional[Dict[str, Any]] = None,
) -> EnhancedJudgeInput:
    """
    Create EnhancedJudgeInput from oracle data and MCP analysis.

    This is a convenience function for integrating with the dashboard.
    """
    return EnhancedJudgeInput(
        task_id=task_id,
        task_description=task_description,
        code_changes=code_changes,
        tool_calls=tool_calls,
        reward=reward,
        # Oracle data
        oracle_ground_truth=oracle_data.get("ground_truth"),
        oracle_expected_approach=oracle_data.get("expected_approach"),
        oracle_evaluation_criteria=oracle_data.get("evaluation_criteria"),
        oracle_context_files=oracle_data.get("context_files"),
        # MCP analysis
        mcp_tools_used=mcp_analysis.get("sourcegraph_tools_used")
        if mcp_analysis
        else None,
        mcp_effectiveness_score=mcp_analysis.get("effectiveness_score")
        if mcp_analysis
        else None,
        mcp_recommendations=mcp_analysis.get("recommendations")
        if mcp_analysis
        else None,
        # Metadata
        task_category=oracle_data.get("task_category"),
        difficulty=oracle_data.get("difficulty"),
    )
