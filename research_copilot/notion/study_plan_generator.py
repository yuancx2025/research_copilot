"""
Study Plan Generator for Notion integration.

Generates structured study plans from research artifacts collected
during user queries, using Pydantic models for type safety.
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
from research_copilot.core.llm_utils import extract_content_as_string
from research_copilot.notion.parsers import call_llm_and_parse_list
from research_copilot.notion.schemas import (
    StudyPlan, Phase, LearningUnit, Citation, Resource
)
from research_copilot.notion.study_plan_prompts import (
    get_objectives_prompt,
    get_key_concepts_prompt,
    get_atomic_units_prompt,
    get_phases_prompt,
    get_next_steps_prompt
)
from research_copilot.notion.parsers import parse_bullets, parse_json_list
import logging
import json
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class StudyPlanGenerator:
    """
    Generates structured study plans from research data.
    
    Takes research artifacts (citations, agent results, answers) and
    generates a comprehensive study plan with learning objectives,
    phases, resources, and next steps.
    """
    
    def __init__(self, llm, config):
        """
        Initialize Study Plan Generator.
        
        Args:
            llm: LLM instance for generating content
            config: Configuration object
        """
        self.llm = llm
        self.config = config
    
    def generate_study_plan(
        self,
        research_data: Dict[str, Any],
        query: str
    ) -> StudyPlan:
        """
        Generate a complete study plan from research data.
        
        Args:
            research_data: Dict containing:
                - citations: List of citation dictionaries
                - agent_results: Dict of agent results by source type
                - answer_text: Generated answer/summary (optional)
            query: User's original research question
        
        Returns:
            StudyPlan Pydantic model
        """
        citations = research_data.get("citations", [])
        agent_results = research_data.get("agent_results", {})
        answer_text = research_data.get("answer_text", "")
        
        # Extract overview from answer text or generate summary
        overview = self._extract_overview(answer_text, citations, query)
        
        # Generate outcome-level objectives (for checkboxes)
        outcome_objectives = self._extract_objectives(answer_text, citations, outcome_format=True)
        
        # Generate phases with atomic learning units
        phases = self._generate_phases(citations, agent_results, answer_text)
        
        # Organize resources by source and convert to Citation models
        organized_citations = self._organize_resources_by_source(citations)
        
        # Generate next steps
        next_steps = self._create_next_steps(citations, outcome_objectives)
        
        return StudyPlan(
            title=f"Study Plan: {query}",
            overview=overview,
            outcome_objectives=outcome_objectives,
            phases=phases,
            citations=organized_citations,
            next_steps=next_steps
        )
    
    def _extract_overview(
        self,
        answer_text: str,
        citations: List[Dict[str, Any]],
        query: str
    ) -> str:
        """Extract or generate overview section."""
        if answer_text and len(answer_text) > 100:
            overview = answer_text.split("\n\n")[0]
            if len(overview) > 500:
                overview = overview[:500] + "..."
            return overview
        
        citation_count = len(citations)
        source_types = set(c.get("source_type", "unknown") for c in citations)
        sources_str = ", ".join(sorted(source_types))
        
        return (
            f"This study plan is based on research about '{query}'. "
            f"Found {citation_count} resource(s) from {sources_str} sources. "
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}."
        )
    
    def _extract_objectives(
        self,
        answer_text: str,
        citations: List[Dict[str, Any]],
        outcome_format: bool = False
    ) -> List[str]:
        """Extract objectives using LLM (outcome format or regular format)."""
        if not answer_text:
            return self._generate_default_objectives(citations, outcome_format)
        
        prompt = get_objectives_prompt(answer_text, outcome_format)
        
        def fallback():
            return self._generate_default_objectives(citations, outcome_format)
        
        objectives = call_llm_and_parse_list(self.llm, prompt, max_items=5, fallback_func=fallback)
        
        # Ensure outcome format starts with "I can"
        if outcome_format:
            objectives = [
                obj if obj.startswith("I can") else f"I can {obj}"
                for obj in objectives
            ]
        
        return objectives[:5] if objectives else fallback()
    
    def _generate_default_objectives(self, citations: List[Dict[str, Any]], outcome_format: bool = False) -> List[str]:
        """Generate default objectives from citation source types."""
        objectives = []
        source_types = set(c.get("source_type", "unknown") for c in citations)
        
        if outcome_format:
            if "arxiv" in source_types:
                objectives.append("I can explain key research papers without notes")
            if "youtube" in source_types:
                objectives.append("I can apply concepts from video tutorials")
            if "github" in source_types:
                objectives.append("I can understand and modify code implementations")
            if "web" in source_types:
                objectives.append("I can summarize key concepts from articles")
            
            if not objectives:
                objectives.extend([
                    "I can explain core concepts without notes",
                    "I can apply the learned material practically"
                ])
        else:
            if "arxiv" in source_types:
                objectives.append("Read and understand key research papers")
            if "youtube" in source_types:
                objectives.append("Watch educational videos and tutorials")
            if "github" in source_types:
                objectives.append("Explore code implementations and examples")
            if "web" in source_types:
                objectives.append("Review articles and documentation")
            
            if not objectives:
                objectives.extend([
                    "Study the collected research materials",
                    "Understand key concepts and applications"
                ])
        
        return objectives[:5]
    
    def _extract_key_concepts_flat(
        self,
        citations: List[Dict[str, Any]],
        agent_results: Dict[str, Any]
    ) -> List[str]:
        """Extract key concepts as flat list."""
        if not citations:
            return ["Core concepts", "Practical applications", "Best practices"]
        
        citation_titles = [c.get("title", "") for c in citations[:10]]
        citation_snippets = [c.get("snippet", "")[:200] for c in citations[:10]]
        
        context = "\n".join([
            f"Title: {title}\nSnippet: {snippet}"
            for title, snippet in zip(citation_titles, citation_snippets)
            if title
        ])
        
        prompt = get_key_concepts_prompt(context)
        
        def fallback():
            return self._generate_default_concepts(citations)
        
        concepts = call_llm_and_parse_list(self.llm, prompt, max_items=10, fallback_func=fallback)
        return concepts[:10] if concepts else fallback()
    
    def _generate_default_concepts(self, citations: List[Dict[str, Any]]) -> List[str]:
        """Generate default concepts from citation titles."""
        concepts = set()
        
        for citation in citations:
            title = citation.get("title", "").lower()
            if title:
                words = title.split()
                common_words = {"the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with", "from"}
                important_words = [w for w in words if w.lower() not in common_words and len(w) > 3]
                concepts.update(important_words[:3])
        
        concepts_list = list(concepts)[:10]
        if len(concepts_list) < 3:
            concepts_list.extend(["Core concepts", "Practical applications", "Best practices"])
        
        return concepts_list[:8]
    
    def _generate_phases(
        self,
        citations: List[Dict[str, Any]],
        agent_results: Dict[str, Any],
        answer_text: str
    ) -> List[Phase]:
        """Generate learning phases with atomic learning units."""
        if not citations:
            return [Phase(
                phase_number=0,
                name="Getting Started",
                time_estimate="1-2 days",
                phase_checkpoint="☐ I completed Phase 0",
                topics=[]
            )]
        
        atomic_units = self._create_atomic_learning_units(citations, agent_results, answer_text)
        
        if not atomic_units:
            return self._fallback_phases(citations)
        
        try:
            return self._group_units_into_phases(atomic_units, citations, answer_text)
        except Exception as e:
            logger.warning(f"Failed to generate phases with LLM: {e}")
            return self._fallback_phases(citations, atomic_units)
    
    def _create_atomic_learning_units(
        self,
        citations: List[Dict[str, Any]],
        agent_results: Dict[str, Any],
        answer_text: str
    ) -> List[LearningUnit]:
        """Create atomic learning units (structured topics) from research data."""
        if not citations:
            return []
        
        concept_names = self._extract_key_concepts_flat(citations, agent_results)
        if not concept_names:
            return []
        
        citation_titles = [c.get("title", "") for c in citations[:15]]
        citation_urls = [c.get("url", "") for c in citations[:15]]
        citation_snippets = [c.get("snippet", "")[:200] for c in citations[:15]]
        citation_types = [c.get("source_type", "unknown") for c in citations[:15]]
        
        context = "\n".join([
            f"{i+1}. {title}\n   Type: {c_type}\n   URL: {url}\n   Snippet: {snippet[:150]}"
            for i, (title, c_type, url, snippet) in enumerate(zip(citation_titles, citation_types, citation_urls, citation_snippets))
            if title
        ])
        
        concepts_text = "\n".join([f"- {concept}" for concept in concept_names[:10]])
        
        prompt = get_atomic_units_prompt(context, concepts_text)
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            response_text = extract_content_as_string(response).strip()
            
            # Extract JSON array from response
            units = parse_json_list(response_text)
            if not units:
                units = self._parse_units_from_text(response_text, concept_names, citations)
            
            # Convert to LearningUnit models
            cleaned_units = []
            for unit in units[:10]:
                if isinstance(unit, dict):
                    # Convert resources to Resource models
                    key_resources = [
                        Resource(
                            title=r.get("title", "")[:80],
                            url=r.get("url", ""),
                            type=r.get("type", "web")
                        )
                        for r in unit.get("key_resources", [])[:3]
                    ]
                    
                    deep_dive_resources = [
                        Resource(
                            title=r.get("title", "")[:80],
                            url=r.get("url", ""),
                            type=r.get("type", "web")
                        )
                        for r in unit.get("deep_dive_resources", unit.get("optional_deep_dive", []))[:2]
                    ]
                    
                    checkpoints = unit.get("checkpoints", unit.get("checkpoint", []))
                    if isinstance(checkpoints, str):
                        checkpoints = [checkpoints]
                    if not checkpoints:
                        checkpoints = [
                            "I can explain this without notes",
                            "I know when to use this concept"
                        ]
                    
                    cleaned_units.append(LearningUnit(
                        name=unit.get("name", unit.get("topic_name", "Unknown Topic")),
                        why_it_matters=unit.get("why_it_matters", "Important concept to understand."),
                        core_ideas=unit.get("core_ideas", [])[:5],
                        key_resources=key_resources,
                        deep_dive_resources=deep_dive_resources,
                        checkpoints=checkpoints[:3]
                    ))
            
            return cleaned_units if cleaned_units else self._fallback_atomic_units(concept_names, citations)
        except Exception as e:
            logger.warning(f"Failed to create atomic learning units with LLM: {e}")
            return self._fallback_atomic_units(concept_names, citations)
    
    def _parse_units_from_text(
        self,
        text: str,
        concept_names: List[str],
        citations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fallback parser for units if JSON parsing fails."""
        units = []
        for concept in concept_names[:8]:
            relevant_citations = [
                c for c in citations[:5]
                if concept.lower() in c.get("title", "").lower() or concept.lower() in c.get("snippet", "").lower()
            ]
            if not relevant_citations:
                relevant_citations = citations[:2]
            
            key_resources = []
            for cit in relevant_citations[:3]:
                key_resources.append({
                    "type": cit.get("source_type", "web"),
                    "title": cit.get("title", "")[:80],
                    "url": cit.get("url", "")
                })
            
            units.append({
                "name": concept,
                "why_it_matters": f"{concept} is a fundamental concept that forms the basis for understanding more advanced topics.",
                "core_ideas": [
                    f"Core principles of {concept}",
                    f"Key applications and use cases",
                    f"Important considerations"
                ],
                "key_resources": key_resources,
                "deep_dive_resources": [],
                "checkpoints": [
                    "I can explain this without notes",
                    "I know when to use this concept"
                ]
            })
        return units
    
    def _fallback_atomic_units(
        self,
        concept_names: List[str],
        citations: List[Dict[str, Any]]
    ) -> List[LearningUnit]:
        """Generate simple atomic units as fallback."""
        units = []
        for concept in concept_names[:8]:
            relevant_citations = [
                c for c in citations[:5]
                if concept.lower() in c.get("title", "").lower()
            ]
            if not relevant_citations:
                relevant_citations = citations[:2] if citations else []
            
            key_resources = [
                Resource(
                    title=cit.get("title", "")[:80],
                    url=cit.get("url", ""),
                    type=cit.get("source_type", "web")
                )
                for cit in relevant_citations[:3]
            ]
            
            units.append(LearningUnit(
                name=concept,
                why_it_matters=f"{concept} is an important concept to understand.",
                core_ideas=[
                    f"Understanding {concept}",
                    f"Applications of {concept}",
                    f"Key principles"
                ],
                key_resources=key_resources,
                deep_dive_resources=[],
                checkpoints=[
                    "I can explain this without notes",
                    "I know when to use this concept"
                ]
            ))
        return units
    
    def _group_units_into_phases(
        self,
        atomic_units: List[LearningUnit],
        citations: List[Dict[str, Any]],
        answer_text: str
    ) -> List[Phase]:
        """Group atomic learning units into logical phases using LLM."""
        units_summary = "\n".join([
            f"{i+1}. {unit.name}: {unit.why_it_matters[:100]}"
            for i, unit in enumerate(atomic_units)
        ])
        
        resource_counts = {
            "arxiv": sum(1 for c in citations if c.get("source_type") == "arxiv"),
            "youtube": sum(1 for c in citations if c.get("source_type") == "youtube"),
            "github": sum(1 for c in citations if c.get("source_type") == "github"),
            "web": sum(1 for c in citations if c.get("source_type") == "web")
        }
        
        prompt = get_phases_prompt(units_summary, resource_counts)
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            response_text = extract_content_as_string(response).strip()
            
            phase_data = parse_json_list(response_text)
            if not phase_data:
                return self._fallback_phases(citations, atomic_units)
            
            # Map units to phases
            phases = []
            unit_map = {unit.name: unit for unit in atomic_units}
            
            for phase_info in phase_data:
                topic_names = phase_info.get("topic_names", [])
                phase_units = [unit_map[name] for name in topic_names if name in unit_map]
                
                if phase_units:
                    phases.append(Phase(
                        phase_number=phase_info.get("phase_number", len(phases)),
                        name=phase_info.get("name", f"Phase {len(phases)}"),
                        time_estimate=phase_info.get("time_estimate", "2-3 days"),
                        topics=phase_units,
                        phase_checkpoint=f"☐ I completed Phase {phase_info.get('phase_number', len(phases))}"
                    ))
            
            return phases if phases else self._fallback_phases(citations, atomic_units)
        except Exception as e:
            logger.warning(f"Failed to group units into phases: {e}")
            return self._fallback_phases(citations, atomic_units)
    
    def _fallback_phases(
        self,
        citations: List[Dict[str, Any]],
        atomic_units: Optional[List[LearningUnit]] = None
    ) -> List[Phase]:
        """Generate simple phases as fallback."""
        if atomic_units is None:
            atomic_units = self._fallback_atomic_units(
                self._extract_key_concepts_flat(citations, {}),
                citations
            )
        
        if not atomic_units:
            return [Phase(
                phase_number=0,
                name="Getting Started",
                time_estimate="1-2 days",
                phase_checkpoint="☐ I completed Phase 0",
                topics=[]
            )]
        
        num_phases = min(3, max(2, len(atomic_units) // 3 + 1))
        units_per_phase = len(atomic_units) // num_phases
        
        phases = []
        phase_names = ["Prerequisites", "Core Foundations", "Advanced Topics"]
        
        for i in range(num_phases):
            start_idx = i * units_per_phase
            end_idx = start_idx + units_per_phase if i < num_phases - 1 else len(atomic_units)
            phase_units = atomic_units[start_idx:end_idx]
            
            if phase_units:
                phases.append(Phase(
                    phase_number=i,
                    name=phase_names[i] if i < len(phase_names) else f"Phase {i}",
                    time_estimate="2-3 days" if i > 0 else "½–1 day",
                    topics=phase_units,
                    phase_checkpoint=f"☐ I completed Phase {i}"
                ))
        
        return phases if phases else [Phase(
            phase_number=0,
            name="Learning Topics",
            time_estimate="2-3 days",
            phase_checkpoint="☐ I completed Phase 0",
            topics=atomic_units
        )]
    
    def _organize_resources_by_source(
        self,
        citations: List[Dict[str, Any]]
    ) -> List[Citation]:
        """
        Organize citations by source type and deduplicate.
        
        Handles citation deduplication once:
        - Canonicalize URLs (normalize arxiv URLs, remove query params/fragments)
        - Drop low-quality entries (YouTube transcript IDs, etc.)
        - Convert to Citation Pydantic models
        
        Returns clean, deduplicated List[Citation] (not dicts).
        """
        if not citations:
            return []
        
        seen_citations = set()
        deduplicated = []
        
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            
            citation_url = citation.get("url", "").strip()
            citation_title = citation.get("title", "").strip()
            
            # Canonicalize URL
            if citation_url:
                citation_url = citation_url.rstrip('/').split('#')[0].split('?')[0]
                if "arxiv.org" in citation_url:
                    arxiv_match = re.search(r'arxiv\.org/(?:pdf|abs|html)/([\d.]+)(?:v\d+)?', citation_url)
                    if arxiv_match:
                        arxiv_id = arxiv_match.group(1)
                        citation_url = f"https://arxiv.org/abs/{arxiv_id}"
            
            citation_key = (citation_url.lower(), citation_title.lower())
            
            if citation_key in seen_citations:
                continue
            
            # Drop low-quality entries (YouTube transcript IDs)
            if citation.get("source_type") == "youtube":
                title_lower = citation_title.lower()
                if title_lower.startswith("transcript:") or (
                    len(citation_title) <= 15 and 
                    citation_title.replace("_", "").replace("-", "").isalnum()
                ):
                    continue
            
            seen_citations.add(citation_key)
            
            # Convert to Citation model
            deduplicated.append(Citation(
                source_type=citation.get("source_type", "unknown"),
                title=citation_title,
                url=citation_url if citation_url else citation.get("url", ""),
                snippet=citation.get("snippet", ""),
                metadata={
                    k: v for k, v in citation.items()
                    if k not in ["source_type", "title", "url", "snippet"]
                }
            ))
        
        return deduplicated
    
    def _create_next_steps(
        self,
        citations: List[Dict[str, Any]],
        learning_objectives: List[str]
    ) -> List[str]:
        """Generate next steps/action items using LLM."""
        if not citations:
            return [
                "Review all collected resources",
                "Take notes on key concepts",
                "Practice with examples or exercises"
            ]
        
        top_resources = []
        arxiv_citations = [c for c in citations if c.get("source_type") == "arxiv"]
        youtube_citations = [c for c in citations if c.get("source_type") == "youtube"]
        github_citations = [c for c in citations if c.get("source_type") == "github"]
        web_citations = [c for c in citations if c.get("source_type") == "web"]
        
        if arxiv_citations:
            top_resources.append(f"Paper: {arxiv_citations[0].get('title', '')[:60]}")
        if youtube_citations:
            top_resources.append(f"Video: {youtube_citations[0].get('title', '')[:60]}")
        if github_citations:
            top_resources.append(f"Repository: {github_citations[0].get('title', '')[:60]}")
        if web_citations:
            top_resources.append(f"Article: {web_citations[0].get('title', '')[:60]}")
        
        objectives_text = "\n".join([f"- {obj}" for obj in learning_objectives[:5]])
        resources_text = "\n".join(top_resources[:5])
        
        prompt = get_next_steps_prompt(objectives_text, resources_text)
        
        def fallback():
            return self._fallback_next_steps(citations)
        
        steps = call_llm_and_parse_list(self.llm, prompt, max_items=6, fallback_func=fallback)
        return steps[:6] if steps else fallback()
    
    def _fallback_next_steps(self, citations: List[Dict[str, Any]]) -> List[str]:
        """Fallback next steps generation."""
        next_steps = []
        
        arxiv_citations = [c for c in citations if c.get("source_type") == "arxiv"]
        youtube_citations = [c for c in citations if c.get("source_type") == "youtube"]
        github_citations = [c for c in citations if c.get("source_type") == "github"]
        
        if arxiv_citations:
            top_paper = arxiv_citations[0]
            paper_title = top_paper.get("title", "key papers")
            next_steps.append(f"Read '{paper_title[:50]}...' paper")
        
        if youtube_citations:
            top_video = youtube_citations[0]
            video_title = top_video.get("title", "video tutorials")
            next_steps.append(f"Watch '{video_title[:50]}...' video")
        
        if github_citations:
            top_repo = github_citations[0]
            repo_name = top_repo.get("title", "repositories")
            next_steps.append(f"Explore '{repo_name[:50]}...' repository")
        
        if len(next_steps) < 3:
            next_steps.extend([
                "Review all collected resources",
                "Take notes on key concepts",
                "Practice with examples or exercises"
            ])
        
        return next_steps[:6]

