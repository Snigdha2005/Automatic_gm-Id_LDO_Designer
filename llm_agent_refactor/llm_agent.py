"""
llm_agent.py
============
LLM-powered agent that:
  1. Accepts free-text application descriptions OR structured spec dicts.
  2. Decides topology (internal vs external compensation).
  3. Converts application text → spec dictionary.
  4. Interacts with the user when no valid design is found, suggesting
     targeted spec relaxations (PSRR, UGB, Iload, etc.).

All Claude API calls go through the Anthropic /v1/messages endpoint.
"""

from __future__ import annotations

import json
import re
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_URL = "https://api.anthropic.com/v1/messages"
MODEL   = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024

HEADERS = {
    "Content-Type": "application/json",
    # API key injected by the runtime – do NOT hard-code here
}

# ---------------------------------------------------------------------------
# Low-level helper
# ---------------------------------------------------------------------------

def _call_claude(system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    """Send a single-turn message to the Claude API and return text."""
    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    # Extract text block
    for block in data.get("content", []):
        if block.get("type") == "text":
            return block["text"].strip()
    return ""


def _extract_json(text: str) -> dict:
    """
    Pull the first JSON object out of a Claude response, even if it is
    wrapped in markdown fences.
    """
    # Strip ```json ... ``` fences if present
    cleaned = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    # Find the first { ... } block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response:\n{text}")
    return json.loads(match.group())


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_SYSTEM_TOPOLOGY = """
You are an expert analog IC designer specialising in LDO regulators.

Given a free-text description of an application or set of requirements, you must:
1. Select the best LDO compensation topology: "internal" (Miller / internally
   compensated) or "external" (externally compensated with an output cap ESR zero).
2. Justify your choice in 1-2 sentences.
3. Extract a complete specification dictionary.

Topology selection rules (apply strictly):
- Use "external" when: output capacitor > 1 µF, load current > 50 mA,
  ESR zero stabilisation is natural, or board-level output cap is mandatory.
- Use "internal" when: on-chip integration is required, output cap < 1 µF,
  low quiescent current < 500 µA, or the application is IoT/wearable.

Required spec keys and their units:
  Vin         [V]      – input voltage
  Vout        [V]      – output voltage
  Iload|max   [mA]     – maximum load current
  Iload|min   [mA]     – minimum (quiescent-state) load current
  Iquiescent  [µA]     – LDO bias / quiescent current
  Cload       [µF]     – output load capacitor
  PSRR        [dB]     – target PSRR at low frequency
  fom         [int]    – figure of merit: 1 = loop-gain error, 2 = fp1 error
  iterations  [int]    – gm/Id sweep iterations (default 20)
  External    [int]    – 1 if external compensation, 0 if internal

Respond with ONLY a valid JSON object in this exact format (no prose, no fences):
{
  "topology": "internal" | "external",
  "justification": "<1-2 sentences>",
  "spec": {
    "Vin": <float>,
    "Vout": <float>,
    "Iload|max": <float>,
    "Iload|min": <float>,
    "Iquiescent": <float>,
    "Cload": <float>,
    "PSRR": <float>,
    "fom": <int>,
    "iterations": <int>,
    "External": <int>
  }
}
"""

_SYSTEM_RELAX = """
You are an expert analog IC designer helping a user relax an LDO specification
when the automated sizing tool could not find a valid design point.

Given:
- The original specification dictionary
- The failure reason (no valid gm/Id found, Cc negative, devices not in saturation, etc.)

Suggest 3 concrete, targeted relaxations.  For each:
- State exactly which spec parameter to change
- Give the new suggested value (e.g. "reduce PSRR from 60 dB to 55 dB")
- Explain in one sentence why this helps

Respond ONLY as a JSON object:
{
  "failure_summary": "<brief explanation of why sizing failed>",
  "relaxations": [
    {
      "parameter": "<spec key>",
      "current_value": <number>,
      "suggested_value": <number>,
      "reason": "<one sentence>"
    },
    ...
  ]
}
"""

_SYSTEM_VALIDATE = """
You are an expert analog IC designer.
Given a specification dictionary, check it for physical plausibility:
- Vin must be > Vout + 0.2 V (minimum dropout)
- Iload|min must be < Iload|max
- Iquiescent should be < Iload|max / 10 for efficiency
- PSRR should be between 20 dB and 80 dB
- Cload should be between 0.01 µF and 100 µF

Return a JSON object:
{
  "valid": true | false,
  "issues": ["<issue 1>", "<issue 2>", ...]
}
If there are no issues, "issues" should be an empty list.
"""


# ---------------------------------------------------------------------------
# Public agent functions
# ---------------------------------------------------------------------------

def parse_input(user_input: str) -> dict:
    """
    Accept either:
      (a) a free-text application description → topology + spec dict
      (b) a JSON / Python-dict-like string    → parse directly, infer topology

    Returns
    -------
    dict with keys: 'topology', 'justification', 'spec'
    """
    # Try direct JSON parse first (user pasted a spec dict)
    try:
        maybe_json = _extract_json(user_input)
        # If it already has the right shape, infer topology and return
        if "Vin" in maybe_json:
            topology_info = _infer_topology_from_spec(maybe_json)
            return {
                "topology":      topology_info["topology"],
                "justification": topology_info["justification"],
                "spec":          {**maybe_json, "External": topology_info["external_flag"]},
            }
    except (ValueError, json.JSONDecodeError):
        pass  # Not JSON – treat as natural language

    # Natural language → Claude
    raw = _call_claude(_SYSTEM_TOPOLOGY, user_input, max_tokens=800)
    result = _extract_json(raw)
    # Ensure External flag is consistent with topology string
    result["spec"]["External"] = 1 if result["topology"] == "external" else 0
    return result


def _infer_topology_from_spec(spec: dict) -> dict:
    """Ask Claude to pick a topology given a raw spec dict."""
    prompt = (
        "Given this LDO spec dictionary, choose the best topology:\n"
        + json.dumps(spec, indent=2)
    )
    raw = _call_claude(_SYSTEM_TOPOLOGY, prompt, max_tokens=600)
    result = _extract_json(raw)
    return {
        "topology":      result["topology"],
        "justification": result.get("justification", ""),
        "external_flag": 1 if result["topology"] == "external" else 0,
    }


def validate_spec(spec: dict) -> dict:
    """
    Validate a spec dict for physical plausibility.

    Returns
    -------
    dict: {"valid": bool, "issues": [str, ...]}
    """
    prompt = "Validate this LDO spec:\n" + json.dumps(spec, indent=2)
    raw = _call_claude(_SYSTEM_VALIDATE, prompt, max_tokens=400)
    return _extract_json(raw)


def suggest_relaxations(spec: dict, failure_reason: str) -> dict:
    """
    When no valid design is found, ask Claude to suggest spec relaxations.

    Parameters
    ----------
    spec           : current specification dictionary
    failure_reason : human-readable description of why sizing failed

    Returns
    -------
    dict: {"failure_summary": str, "relaxations": [{"parameter", "current_value",
            "suggested_value", "reason"}, ...]}
    """
    prompt = (
        f"Original spec:\n{json.dumps(spec, indent=2)}\n\n"
        f"Failure reason: {failure_reason}"
    )
    raw = _call_claude(_SYSTEM_RELAX, prompt, max_tokens=600)
    return _extract_json(raw)


def format_relaxation_prompt(relaxation_info: dict) -> str:
    """
    Convert the structured relaxation dict into a friendly user-facing prompt
    (the "reduce PSRR by 5%?" style message).
    """
    lines = [
        f"\n⚠️  No valid design found.",
        f"   {relaxation_info['failure_summary']}",
        "",
        "💡 Suggested spec relaxations:",
    ]
    for i, r in enumerate(relaxation_info["relaxations"], 1):
        lines.append(
            f"   [{i}] Change '{r['parameter']}' from {r['current_value']} "
            f"→ {r['suggested_value']}  ({r['reason']})"
        )
    lines += [
        "",
        "Enter the number of the relaxation to apply (or 'skip' to abort): ",
    ]
    return "\n".join(lines)


def apply_relaxation(spec: dict, relaxation_info: dict, choice: int) -> dict:
    """
    Apply one of the suggested relaxations to the spec dict.

    Parameters
    ----------
    spec            : current spec
    relaxation_info : output of suggest_relaxations()
    choice          : 1-based index of the chosen relaxation

    Returns
    -------
    Updated spec dict.
    """
    new_spec = dict(spec)
    idx = choice - 1
    if idx < 0 or idx >= len(relaxation_info["relaxations"]):
        raise IndexError(f"Invalid choice {choice}")
    r = relaxation_info["relaxations"][idx]
    new_spec[r["parameter"]] = r["suggested_value"]
    print(f"✅  Applied: '{r['parameter']}' = {r['suggested_value']}")
    return new_spec
