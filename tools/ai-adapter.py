#!/usr/bin/env python3
"""
AI Adapter - Task-based text processing utility for the system.

Processes input data through task-specific handlers using prompt templates.
Supports summarization, text polishing, and diff simplification.

Usage:
    python ai-adapter.py --task summarize_daily --in input.json --out output.json
"""
import argparse
import json
import os
import sys
import re
from pathlib import Path
from typing import Any, Dict, Optional, Callable

VERSION = "1.1.0"

def load_prompt(prompts_dir: str, task: str) -> Optional[str]:
    """Load prompt template for the given task."""
    prompt_path = Path(prompts_dir) / f"{task}.txt"
    if prompt_path.exists():
        content = prompt_path.read_text().strip()
        return content if content else None
    return None

def extract_key_sentences(text: str, max_sentences: int = 5) -> str:
    """Extract the most important sentences from text."""
    if not text:
        return ""
    sentences = re.split(r'[.!?]+\s*', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= max_sentences:
        return '. '.join(sentences) + '.' if sentences else ""
    # Prioritize longer sentences as more likely to be informative
    scored = [(len(s.split()), s) for s in sentences]
    scored.sort(reverse=True)
    selected = [s for _, s in scored[:max_sentences]]
    return '. '.join(selected) + '.'

def summarize_entries(entries: list, level: str = "daily") -> Dict[str, Any]:
    """Summarize a list of entries based on summarization level."""
    if not entries:
        return {"summary": "No entries to summarize.", "entry_count": 0}

    combined_text = " ".join(
        str(e.get("content", e.get("message", e.get("text", str(e)))))
        for e in entries
    )

    max_sentences = {"daily": 5, "monthly": 10, "yearly": 15}.get(level, 5)
    summary = extract_key_sentences(combined_text, max_sentences)

    return {
        "summary": summary or "Entries processed successfully.",
        "entry_count": len(entries),
        "level": level
    }

def polish_text(text: str) -> Dict[str, Any]:
    """Polish text by cleaning formatting and improving readability."""
    if not text:
        return {"polished": "", "changes": []}

    changes = []
    polished = text

    # Remove multiple spaces
    new_text = re.sub(r' +', ' ', polished)
    if new_text != polished:
        changes.append("normalized_whitespace")
        polished = new_text

    # Fix common punctuation issues
    new_text = re.sub(r'\s+([.,!?;:])', r'\1', polished)
    if new_text != polished:
        changes.append("fixed_punctuation_spacing")
        polished = new_text

    # Ensure sentence capitalization
    sentences = re.split(r'([.!?]+\s*)', polished)
    result_parts = []
    for i, part in enumerate(sentences):
        if i > 0 and result_parts and result_parts[-1] and result_parts[-1][-1] in '.!?':
            part = part.lstrip()
            if part:
                part = part[0].upper() + part[1:] if len(part) > 1 else part.upper()
                if part[0].isupper() and part[0] != sentences[i][0]:
                    changes.append("capitalized_sentence")
        result_parts.append(part)
    polished = ''.join(result_parts).strip()

    return {
        "polished": polished,
        "original_length": len(text),
        "polished_length": len(polished),
        "changes": list(set(changes))
    }

def simplify_diff(diff_content: str) -> Dict[str, Any]:
    """Simplify a diff for human readability."""
    if not diff_content:
        return {"simplified": "", "stats": {}}

    lines = diff_content.split('\n')
    additions = [l for l in lines if l.startswith('+') and not l.startswith('+++')]
    deletions = [l for l in lines if l.startswith('-') and not l.startswith('---')]

    summary_parts = []
    if additions:
        summary_parts.append(f"Added {len(additions)} line(s)")
    if deletions:
        summary_parts.append(f"Removed {len(deletions)} line(s)")

    simplified = "; ".join(summary_parts) if summary_parts else "No changes detected."

    return {
        "simplified": simplified,
        "stats": {
            "additions": len(additions),
            "deletions": len(deletions),
            "total_lines": len(lines)
        }
    }

def diary_bullet(entries: list) -> Dict[str, Any]:
    """Convert entries to bullet point format."""
    bullets = []
    for entry in entries:
        if isinstance(entry, dict):
            text = entry.get("content", entry.get("message", entry.get("text", "")))
        else:
            text = str(entry)
        if text:
            # Clean and truncate for bullet
            clean = text.strip().replace('\n', ' ')[:100]
            bullets.append(f"• {clean}")

    return {
        "bullets": bullets,
        "count": len(bullets)
    }

def failover_truncate(text: str, max_length: int = 500) -> Dict[str, Any]:
    """Failover handler that truncates text to max length."""
    if not text:
        return {"truncated": "", "was_truncated": False}

    truncated = text[:max_length]
    was_truncated = len(text) > max_length
    if was_truncated:
        truncated = truncated.rsplit(' ', 1)[0] + "..."

    return {
        "truncated": truncated,
        "original_length": len(text),
        "truncated_length": len(truncated),
        "was_truncated": was_truncated
    }

# Task handler registry
TASK_HANDLERS: Dict[str, Callable[[Dict], Dict]] = {
    "summarize_daily": lambda d: summarize_entries(d.get("entries", []), "daily"),
    "summarize_monthly": lambda d: summarize_entries(d.get("entries", []), "monthly"),
    "summarize_yearly": lambda d: summarize_entries(d.get("entries", []), "yearly"),
    "polish_commit": lambda d: polish_text(d.get("message", d.get("text", ""))),
    "simplify_diff": lambda d: simplify_diff(d.get("diff", d.get("content", ""))),
    "diary_bullet": lambda d: diary_bullet(d.get("entries", [])),
    "failover_truncate": lambda d: failover_truncate(
        d.get("text", d.get("content", "")),
        d.get("max_length", 500)
    ),
}

def process_task(task: str, data: Dict[str, Any], prompts_dir: str) -> Dict[str, Any]:
    """Process a task with the given input data."""
    prompt = load_prompt(prompts_dir, task)

    handler = TASK_HANDLERS.get(task)
    if handler:
        result = handler(data)
        return {
            "task": task,
            "result": result,
            "prompt_loaded": prompt is not None,
            "failover": False
        }

    # Unknown task - apply failover
    text = data.get("text", data.get("content", data.get("message", "")))
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)
    elif not isinstance(text, str):
        text = str(text)

    failover_result = failover_truncate(text, 1000)
    return {
        "task": task,
        "result": {
            "message": f"Task '{task}' processed via failover handler.",
            "processed": failover_result["truncated"]
        },
        "prompt_loaded": prompt is not None,
        "failover": True
    }

def main():
    # Handle --version and --list-tasks before full argument parsing
    if "--version" in sys.argv:
        print(f"ai-adapter v{VERSION}")
        sys.exit(0)

    if "--list-tasks" in sys.argv:
        print("Available tasks:")
        for task in sorted(TASK_HANDLERS.keys()):
            print(f"  - {task}")
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="AI Adapter - Task-based text processing for the system"
    )
    parser.add_argument("--task", required=True, help="Task to execute")
    parser.add_argument("--in", dest="infile", required=True, help="Input JSON file")
    parser.add_argument("--out", dest="outfile", required=True, help="Output JSON file")
    parser.add_argument(
        "--prompts-dir",
        default="tools/ai-adapter/prompts/v1",
        help="Directory containing prompt templates"
    )
    args = parser.parse_args()

    # Load input
    try:
        with open(args.infile) as f:
            data = json.load(f)
    except FileNotFoundError:
        sys.stderr.write(f"Error: Input file not found: {args.infile}\n")
        sys.exit(1)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Error: Invalid JSON in input file: {e}\n")
        sys.exit(1)

    # Process task
    output = process_task(args.task, data, args.prompts_dir)

    # Write output
    try:
        with open(args.outfile, "w") as f:
            json.dump(output, f, indent=2)
    except IOError as e:
        sys.stderr.write(f"Error: Cannot write output file: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
