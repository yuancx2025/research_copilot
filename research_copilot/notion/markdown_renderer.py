"""Deterministic Markdown representation shared by preview and MCP export."""
from .schemas import StudyPlan


def render_markdown(plan: StudyPlan) -> str:
    lines = [f'# {plan.title}', '', plan.overview, '', '## Objectives', '']
    lines += [f'- [ ] {item}' for item in plan.outcome_objectives]
    for phase in plan.phases:
        lines += ['', f'## Phase {phase.phase_number}: {phase.name}', '', phase.time_estimate, '']
        for topic in phase.topics:
            lines += [f'### {topic.name}', '', topic.why_it_matters, '']
            lines += [f'- {idea}' for idea in topic.core_ideas]
            for label, resources in [('Resources', topic.key_resources), ('Deep dives', topic.deep_dive_resources)]:
                lines += ['', f'**{label}**', '']
                lines += [f'- [{r.title}]({r.url})' for r in resources]
            lines += ['', '**Checkpoints**', ''] + [f'- [ ] {c}' for c in topic.checkpoints]
        lines += ['', f'Phase checkpoint: {phase.phase_checkpoint}']
    lines += ['', '## Sources', ''] + [f'- [{c.title}]({c.url})' for c in plan.citations]
    lines += ['', '## Next steps', ''] + [f'- [ ] {s}' for s in plan.next_steps]
    return '\n'.join(lines)
