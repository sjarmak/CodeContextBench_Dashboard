"""
Cost Calculator

Calculates costs based on token usage and model pricing.
Supports Anthropic models with pricing from:
https://platform.claude.com/docs/en/about-claude/pricing

Can be extended for other providers.
"""

from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class ModelPricing:
    """Model pricing information."""
    input_per_mtok: float  # USD per million tokens
    output_per_mtok: float
    cache_write_per_mtok: float = 0.0
    cache_read_per_mtok: float = 0.0


# Anthropic Claude pricing (as of pricing page)
ANTHROPIC_PRICING = {
    # Claude 4.5 Opus (latest)
    "anthropic/claude-opus-4-5-20251101": ModelPricing(
        input_per_mtok=15.00,
        output_per_mtok=75.00,
        cache_write_per_mtok=18.75,
        cache_read_per_mtok=1.50,
    ),
    "claude-opus-4-5-20251101": ModelPricing(
        input_per_mtok=15.00,
        output_per_mtok=75.00,
        cache_write_per_mtok=18.75,
        cache_read_per_mtok=1.50,
    ),

    # Claude 4.5 Sonnet
    "anthropic/claude-sonnet-4-5-20251101": ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_write_per_mtok=3.75,
        cache_read_per_mtok=0.30,
    ),
    "claude-sonnet-4-5-20251101": ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_write_per_mtok=3.75,
        cache_read_per_mtok=0.30,
    ),

    # Claude 3.5 Sonnet
    "anthropic/claude-sonnet-3-5-20241022": ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_write_per_mtok=3.75,
        cache_read_per_mtok=0.30,
    ),
    "anthropic/claude-sonnet-3-5-20250929": ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_write_per_mtok=3.75,
        cache_read_per_mtok=0.30,
    ),

    # Claude 3.5 Haiku
    "anthropic/claude-haiku-3-5-20241022": ModelPricing(
        input_per_mtok=0.80,
        output_per_mtok=4.00,
        cache_write_per_mtok=1.00,
        cache_read_per_mtok=0.08,
    ),
    "anthropic/claude-haiku-4-5-20251001": ModelPricing(
        input_per_mtok=0.80,
        output_per_mtok=4.00,
        cache_write_per_mtok=1.00,
        cache_read_per_mtok=0.08,
    ),

    # Claude 3 Opus
    "anthropic/claude-opus-3-20240229": ModelPricing(
        input_per_mtok=15.00,
        output_per_mtok=75.00,
        cache_write_per_mtok=18.75,
        cache_read_per_mtok=1.50,
    ),

    # Claude 3 Sonnet (legacy)
    "anthropic/claude-sonnet-3-20240229": ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_write_per_mtok=3.75,
        cache_read_per_mtok=0.30,
    ),

    # Claude 3 Haiku (legacy)
    "anthropic/claude-haiku-3-20240307": ModelPricing(
        input_per_mtok=0.25,
        output_per_mtok=1.25,
        cache_write_per_mtok=0.30,
        cache_read_per_mtok=0.03,
    ),
}

# Aliases for common model names
MODEL_ALIASES = {
    "claude-opus-4-5": "anthropic/claude-opus-4-5-20251101",
    "claude-sonnet-4-5": "anthropic/claude-sonnet-4-5-20251101",
    "claude-haiku-4-5": "anthropic/claude-haiku-4-5-20251001",
    "claude-opus-3": "anthropic/claude-opus-3-20240229",
}


def get_model_pricing(model_name: str) -> Optional[ModelPricing]:
    """
    Get pricing for a model.

    Args:
        model_name: Model identifier (with or without provider prefix)

    Returns:
        ModelPricing if found, None otherwise
    """
    # Normalize model name
    normalized = model_name

    # Check aliases
    if normalized in MODEL_ALIASES:
        normalized = MODEL_ALIASES[normalized]

    # Check if it starts with provider
    if not normalized.startswith("anthropic/"):
        # Try adding anthropic prefix
        if f"anthropic/{normalized}" in ANTHROPIC_PRICING:
            normalized = f"anthropic/{normalized}"

    return ANTHROPIC_PRICING.get(normalized)


def calculate_cost(
    model_name: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> Dict[str, float]:
    """
    Calculate cost for token usage.

    Args:
        model_name: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cache_creation_tokens: Number of cache write tokens
        cache_read_tokens: Number of cache read tokens

    Returns:
        Dictionary with cost breakdown
    """
    pricing = get_model_pricing(model_name)

    if not pricing:
        return {
            "total_cost": 0.0,
            "input_cost": 0.0,
            "output_cost": 0.0,
            "cache_write_cost": 0.0,
            "cache_read_cost": 0.0,
            "error": f"Pricing not found for model: {model_name}",
        }

    # Calculate costs (convert tokens to millions)
    input_cost = (input_tokens / 1_000_000) * pricing.input_per_mtok
    output_cost = (output_tokens / 1_000_000) * pricing.output_per_mtok
    cache_write_cost = (cache_creation_tokens / 1_000_000) * pricing.cache_write_per_mtok
    cache_read_cost = (cache_read_tokens / 1_000_000) * pricing.cache_read_per_mtok

    total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost

    return {
        "total_cost": round(total_cost, 6),
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "cache_write_cost": round(cache_write_cost, 6),
        "cache_read_cost": round(cache_read_cost, 6),
        "total_tokens": input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens,
    }


def calculate_cost_from_result(result_data: Dict) -> Dict[str, float]:
    """
    Calculate cost from Harbor result.json data.

    Args:
        result_data: Loaded result.json dictionary

    Returns:
        Cost breakdown dictionary
    """
    # Extract model name
    config = result_data.get("config", {})
    agent_config = config.get("agent", {})
    model_name = agent_config.get("model_name", "unknown")

    # Extract token usage
    agent_result = result_data.get("agent_result", {})
    input_tokens = agent_result.get("n_input_tokens", 0)
    output_tokens = agent_result.get("n_output_tokens", 0)
    cache_tokens = agent_result.get("n_cache_tokens", 0)

    # Cache tokens might be split into creation and read
    # For now, assume cache_tokens = cache_read_tokens
    # This may need refinement based on Harbor's actual output

    return calculate_cost(
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_tokens,
    )


def add_custom_pricing(model_name: str, pricing: ModelPricing):
    """
    Add custom pricing for a model.

    Args:
        model_name: Model identifier
        pricing: ModelPricing object
    """
    ANTHROPIC_PRICING[model_name] = pricing
