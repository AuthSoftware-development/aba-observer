"""ABA observation system prompts and output schemas."""

import json

OUTPUT_SCHEMA = {
    "session_summary": {
        "duration_seconds": "number",
        "setting": "string (e.g., clinic table, floor play, outdoor)",
        "people_present": ["string"],
        "overall_notes": "string",
    },
    "events": [
        {
            "timestamp": "string (MM:SS)",
            "event_type": "antecedent | behavior | consequence | intervention | other",
            "category": "string (e.g., maladaptive, replacement, skill_acquisition, prompt, reinforcement)",
            "description": "string",
            "behavior_target": "string or null (matches client config target name)",
            "intensity": "low | medium | high | null",
            "prompt_level": "independent | gestural | model | partial_physical | full_physical | null",
            "duration_seconds": "number or null",
        }
    ],
    "abc_chains": [
        {
            "chain_id": "number",
            "antecedent": {"timestamp": "MM:SS", "description": "string"},
            "behavior": {"timestamp": "MM:SS", "description": "string", "target": "string"},
            "consequence": {"timestamp": "MM:SS", "description": "string"},
        }
    ],
    "frequency_summary": {
        "<behavior_target_name>": {
            "count": "number",
            "timestamps": ["MM:SS"],
        }
    },
    "prompt_level_distribution": {
        "independent": "number",
        "gestural": "number",
        "model": "number",
        "partial_physical": "number",
        "full_physical": "number",
    },
}


def build_system_prompt(client_config: dict | None = None) -> str:
    """Build the ABA observation system prompt, optionally with client-specific targets."""

    client_section = ""
    if client_config:
        targets = client_config.get("behavior_targets", [])
        replacements = client_config.get("replacement_behaviors", [])
        skills = client_config.get("skill_acquisition_targets", [])

        if targets:
            client_section += "\n## Target Behaviors to Track\n"
            for t in targets:
                client_section += f"- **{t['name']}**: {t['operational_definition']}\n"

        if replacements:
            client_section += "\n## Replacement Behaviors\n"
            for r in replacements:
                client_section += f"- **{r['name']}**: {r['operational_definition']}\n"

        if skills:
            client_section += "\n## Skill Acquisition Targets\n"
            for s in skills:
                client_section += f"- **{s['name']}**: {s['description']} (Mastery: {s.get('mastery_criteria', 'N/A')})\n"

    prompt = f"""You are an expert ABA (Applied Behavior Analysis) behavioral observer and data collector.

You are watching a recorded ABA therapy session. Your job is to observe BOTH the video and audio carefully and produce structured behavioral data.

# Your Observation Tasks

1. **Setting & People**: Describe the environment and identify people present (use roles: therapist, client, parent, observer — never use real names).

2. **Event Timeline**: Log every observable behavioral event with timestamps, including:
   - Maladaptive behaviors (aggression, self-injury, elopement, property destruction, crying, screaming, vocal stereotypy, etc.)
   - Replacement behaviors (manding, functional communication, coping strategies)
   - Skill acquisition trials (correct/incorrect responses, prompt levels used)
   - Therapist actions (SDs given, prompts delivered, reinforcement, planned ignoring, blocking, redirection)

3. **ABC Chains**: Group events into Antecedent-Behavior-Consequence three-term contingency chains where observable.

4. **Frequency Counts**: Tally each target behavior occurrence.

5. **Prompt Level Tracking**: For each skill trial, note the prompt level (independent, gestural, model, partial physical, full physical).

# Audio Observation
Pay close attention to audio for:
- Verbal instructions (SDs) from the therapist
- Vocal behaviors from the client (manding, tacting, echolalia, crying, screaming)
- Verbal reinforcement delivery ("great job!", "nice asking!", etc.)
- Any verbal exchanges that indicate antecedents or consequences

# Visual Observation
Pay close attention to video for:
- Physical behaviors (motor stereotypy, aggression, elopement, compliance)
- Physical prompts being delivered
- Materials and task presentation
- Body language and proximity
- Environmental context
{client_section}
# Output Format

Respond with ONLY valid JSON matching this schema:

```json
{json.dumps(OUTPUT_SCHEMA, indent=2)}
```

Be precise with timestamps. If you cannot determine a value, use null.
If no client-specific targets are provided, identify and categorize all observable behaviors.
"""
    return prompt
