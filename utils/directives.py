"""
utils/directives.py
Directive Loader — reads policy Markdown files for injection into LLM prompts.

This is the bridge between the Directive layer (directives/*.md) and the
Orchestration layer (agents/*.py). Each agent passes the relevant directive
to its LLM calls so the model reasons within defined business boundaries.

Usage:
    from utils.directives import load_directive
    directive = load_directive("budget")   # loads directives/budget_policy.md
    system_prompt = f"## Policy\\n{directive}\\n\\n{base_system}"
"""

from pathlib import Path

_DIRECTIVE_DIR = Path(__file__).parent.parent / "directives"


def load_directive(name: str) -> str:
    """
    Load a policy Markdown file by domain name.

    Parameters
    ----------
    name : str
        Domain name without suffix, e.g. "budget", "cash", "invoice",
        "credit", "reconciliation".

    Returns
    -------
    str
        Full Markdown content, or empty string if the file doesn't exist.
    """
    path = _DIRECTIVE_DIR / f"{name}_policy.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def inject_directive(base_system: str, domain: str) -> str:
    """
    Prepend the domain directive to an existing system prompt.

    Returns the original system prompt unchanged if no directive file exists.
    """
    directive = load_directive(domain)
    if not directive:
        return base_system
    return f"## Operational Directive\n{directive}\n\n{base_system}"
