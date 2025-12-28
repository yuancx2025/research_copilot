"""
Study Plan Generator for Notion integration.

Generates structured study plans from research artifacts collected
during user queries, formatting them for Notion page creation.
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
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
    key concepts, resources, timeline, and next steps.
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
    ) -> Dict[str, Any]:
        """
        Generate a complete study plan from research data.
        
        Args:
            research_data: Dict containing:
                - citations: List of citation dictionaries
                - agent_results: Dict of agent results by source type
                - answer_text: Generated answer/summary (optional)
            query: User's original research question
        
        Returns:
            Dict with study plan structure:
                - title: Page title
                - overview: Overview text
                - outcome_objectives: List of outcome-level checkboxes
                - phases: List of phase dicts with topics (atomic learning units)
                - citations: List of citations (organized)
                - next_steps: List of action items
                - timeline: List of timeline items (for backward compatibility)
                - learning_objectives: List of objectives (for backward compatibility)
                - key_concepts: List of concepts (for backward compatibility)
        """
        citations = research_data.get("citations", [])
        agent_results = research_data.get("agent_results", {})
        answer_text = research_data.get("answer_text", "")
        
        # Extract overview from answer text or generate summary
        overview = self._extract_overview(answer_text, citations, query)
        
        # Generate outcome-level objectives (for checkboxes)
        outcome_objectives = self._extract_outcome_objectives(answer_text, citations)
        
        # Generate phases with atomic learning units
        phases = self._generate_phases(citations, agent_results, answer_text)
        
        # Organize resources by source
        organized_citations = self._organize_resources_by_source(citations)
        
        # Generate next steps
        next_steps = self._create_next_steps(citations, outcome_objectives)
        
        # Generate legacy fields for backward compatibility
        learning_objectives = self._extract_learning_objectives(answer_text, citations)
        key_concepts = self._extract_key_concepts_flat(citations, agent_results)
        timeline = self._create_timeline(citations, learning_objectives)
        
        return {
            "title": f"Study Plan: {query}",
            "overview": overview,
            "outcome_objectives": outcome_objectives,
            "phases": phases,
            "citations": organized_citations,
            "next_steps": next_steps,
            # Backward compatibility fields
            "timeline": timeline,
            "learning_objectives": learning_objectives,
            "key_concepts": key_concepts
        }
    
    def _extract_overview(
        self,
        answer_text: str,
        citations: List[Dict[str, Any]],
        query: str
    ) -> str:
        """
        Extract or generate overview section.
        
        Args:
            answer_text: Generated answer from research
            citations: List of citations
            query: Original query
        
        Returns:
            Overview text
        """
        if answer_text and len(answer_text) > 100:
            # Use first paragraph of answer as overview
            overview = answer_text.split("\n\n")[0]
            # Limit length
            if len(overview) > 500:
                overview = overview[:500] + "..."
            return overview
        
        # Generate simple overview if no answer text
        citation_count = len(citations)
        source_types = set(c.get("source_type", "unknown") for c in citations)
        sources_str = ", ".join(sorted(source_types))
        
        return (
            f"This study plan is based on research about '{query}'. "
            f"Found {citation_count} resource(s) from {sources_str} sources. "
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}."
        )
    
    def _extract_outcome_objectives(
        self,
        answer_text: str,
        citations: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Extract outcome-level objectives (for checkboxes) using LLM.
        
        Args:
            answer_text: Generated answer from research
            citations: List of citations
        
        Returns:
            List of outcome objective strings (e.g., "I can explain X without notes")
        """
        if not answer_text:
            return self._generate_outcome_objectives_from_citations(citations)
        
        prompt = f"""Based on the following research summary, create 3-5 outcome-level learning objectives.
Each objective should be a checkbox statement starting with "I can" that represents a measurable outcome.

Research Summary:
{answer_text[:1000]}

Examples:
- "I can explain transformers without notes"
- "I can compare 5 modern architectures"
- "I can implement a basic transformer from scratch"

Format as a bulleted list, one objective per line. Each should start with "I can" and be specific and measurable."""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            objectives_text = response.content.strip()
            
            # Parse bulleted list
            objectives = []
            for line in objectives_text.split("\n"):
                line = line.strip()
                # Remove bullet markers
                for marker in ["-", "•", "*", "1.", "2.", "3.", "4.", "5."]:
                    if line.startswith(marker):
                        line = line[len(marker):].strip()
                # Ensure it starts with "I can"
                if line and not line.startswith("I can"):
                    line = f"I can {line}"
                if line:
                    objectives.append(line)
            
            # Limit to 5 objectives
            return objectives[:5] if objectives else self._generate_outcome_objectives_from_citations(citations)
        except Exception as e:
            logger.warning(f"Failed to generate outcome objectives: {e}")
            return self._generate_outcome_objectives_from_citations(citations)
    
    def _generate_outcome_objectives_from_citations(self, citations: List[Dict[str, Any]]) -> List[str]:
        """Generate simple outcome objectives from citations as fallback."""
        objectives = []
        
        source_types = set(c.get("source_type", "unknown") for c in citations)
        
        if "arxiv" in source_types:
            objectives.append("I can explain key research papers without notes")
        if "youtube" in source_types:
            objectives.append("I can apply concepts from video tutorials")
        if "github" in source_types:
            objectives.append("I can understand and modify code implementations")
        if "web" in source_types:
            objectives.append("I can summarize key concepts from articles")
        
        if not objectives:
            objectives.append("I can explain core concepts without notes")
            objectives.append("I can apply the learned material practically")
        
        return objectives[:5]
    
    def _extract_learning_objectives(
        self,
        answer_text: str,
        citations: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Extract learning objectives using LLM (for backward compatibility).
        
        Args:
            answer_text: Generated answer from research
            citations: List of citations
        
        Returns:
            List of learning objective strings
        """
        if not answer_text:
            # Fallback: generate from citations
            return self._generate_objectives_from_citations(citations)
        
        prompt = f"""Based on the following research summary, extract 3-5 key learning objectives.
Each objective should be a clear, actionable statement about what someone should learn.

Research Summary:
{answer_text[:1000]}

Format as a bulleted list, one objective per line. Be specific and actionable."""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            objectives_text = response.content.strip()
            
            # Parse bulleted list
            objectives = []
            for line in objectives_text.split("\n"):
                line = line.strip()
                # Remove bullet markers
                for marker in ["-", "•", "*", "1.", "2.", "3.", "4.", "5."]:
                    if line.startswith(marker):
                        line = line[len(marker):].strip()
                if line:
                    objectives.append(line)
            
            # Limit to 5 objectives
            return objectives[:5] if objectives else self._generate_objectives_from_citations(citations)
        except Exception as e:
            logger.warning(f"Failed to generate learning objectives: {e}")
            return self._generate_objectives_from_citations(citations)
    
    def _generate_objectives_from_citations(self, citations: List[Dict[str, Any]]) -> List[str]:
        """Generate simple objectives from citations as fallback."""
        objectives = []
        
        # Check what types of resources we have
        source_types = set(c.get("source_type", "unknown") for c in citations)
        
        if "arxiv" in source_types:
            objectives.append("Read and understand key research papers")
        if "youtube" in source_types:
            objectives.append("Watch educational videos and tutorials")
        if "github" in source_types:
            objectives.append("Explore code implementations and examples")
        if "web" in source_types:
            objectives.append("Review articles and documentation")
        
        if not objectives:
            objectives.append("Study the collected research materials")
            objectives.append("Understand key concepts and applications")
        
        return objectives[:5]
    
    def _extract_key_concepts_flat(
        self,
        citations: List[Dict[str, Any]],
        agent_results: Dict[str, Any]
    ) -> List[str]:
        """
        Extract key concepts as flat list (for backward compatibility).
        
        Args:
            citations: List of citations
            agent_results: Dict of agent results by source type
        
        Returns:
            List of key concept strings
        """
        if not citations:
            return ["Core concepts", "Practical applications", "Best practices"]
        
        # Build context from citations
        citation_titles = [c.get("title", "") for c in citations[:10]]
        citation_snippets = [c.get("snippet", "")[:200] for c in citations[:10]]
        
        context = "\n".join([
            f"Title: {title}\nSnippet: {snippet}"
            for title, snippet in zip(citation_titles, citation_snippets)
            if title
        ])
        
        prompt = f"""Based on the following research citations, extract 5-10 key concepts that someone should understand.

Research Citations:
{context[:1500]}

Extract key concepts that are:
- Important technical terms or ideas
- Core topics covered in the research
- Concepts that appear across multiple sources

Format as a bulleted list, one concept per line. Be specific and use proper terminology."""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            concepts_text = response.content.strip()
            
            # Parse bulleted list
            concepts = []
            for line in concepts_text.split("\n"):
                line = line.strip()
                # Remove bullet markers
                for marker in ["-", "•", "*", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10."]:
                    if line.startswith(marker):
                        line = line[len(marker):].strip()
                if line and len(line) > 2:
                    concepts.append(line)
            
            # Limit to 10 concepts
            return concepts[:10] if concepts else self._fallback_concepts(citations)
        except Exception as e:
            logger.warning(f"Failed to extract key concepts with LLM: {e}")
            return self._fallback_concepts(citations)
    
    def _fallback_concepts(self, citations: List[Dict[str, Any]]) -> List[str]:
        """Fallback concept extraction using simple heuristics."""
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
    ) -> List[Dict[str, Any]]:
        """
        Generate learning phases with atomic learning units.
        
        Args:
            citations: List of citations
            agent_results: Dict of agent results by source type
            answer_text: Generated answer/summary
        
        Returns:
            List of phase dicts, each containing topics (atomic learning units)
        """
        if not citations:
            # Fallback: create a single phase
            return [{
                "phase_number": 0,
                "name": "Getting Started",
                "time_estimate": "1-2 days",
                "topics": [],
                "phase_checkpoint": "☐ I completed Phase 0"
            }]
        
        # First, create atomic learning units
        atomic_units = self._create_atomic_learning_units(citations, agent_results, answer_text)
        
        if not atomic_units:
            return self._fallback_phases(citations)
        
        # Use LLM to group units into phases
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
    ) -> List[Dict[str, Any]]:
        """
        Create atomic learning units (structured topics) from research data.
        
        Args:
            citations: List of citations
            agent_results: Dict of agent results by source type
            answer_text: Generated answer/summary
        
        Returns:
            List of atomic learning unit dicts
        """
        if not citations:
            return []
        
        # Extract concept names first
        concept_names = self._extract_key_concepts_flat(citations, agent_results)
        if not concept_names:
            return []
        
        # Build context for LLM
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
        
        prompt = f"""Based on the following research citations and key concepts, create atomic learning units.
Each unit should be a self-contained topic that can be learned independently.

Research Citations:
{context[:2000]}

Key Concepts:
{concepts_text}

For each concept (or group of related concepts), create a learning unit with:
1. Topic name (the concept name)
2. Why it matters (2-3 sentences explaining importance in plain English)
3. Core ideas (3-5 bullet points with key ideas)
4. Key resources (map relevant citations to this topic - include type: paper/blog/video, title, url)
5. Optional deep dive resources (1-2 advanced resources if available)
6. Checkpoints (2-3 self-assessment questions like "I can explain this without notes")

Format as JSON array, one unit per concept. Limit to 8-10 units total."""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            response_text = response.content.strip()
            
            # Extract JSON array from response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                units = json.loads(json_match.group(0))
            else:
                # Fallback: parse manually
                units = self._parse_units_from_text(response_text, concept_names, citations)
            
            # Validate and clean units
            cleaned_units = []
            for unit in units[:10]:
                if isinstance(unit, dict):
                    cleaned_unit = {
                        "name": unit.get("name", unit.get("topic_name", "Unknown Topic")),
                        "why_it_matters": unit.get("why_it_matters", unit.get("why_it_matters", "Important concept to understand.")),
                        "core_ideas": unit.get("core_ideas", unit.get("core_ideas", [])),
                        "key_resources": unit.get("key_resources", []),
                        "deep_dive_resources": unit.get("deep_dive_resources", unit.get("optional_deep_dive", [])),
                        "checkpoints": unit.get("checkpoints", unit.get("checkpoint", []))
                    }
                    # Ensure checkpoints are list of strings
                    if isinstance(cleaned_unit["checkpoints"], str):
                        cleaned_unit["checkpoints"] = [cleaned_unit["checkpoints"]]
                    if not cleaned_unit["checkpoints"]:
                        cleaned_unit["checkpoints"] = [
                            "I can explain this without notes",
                            "I know when to use this concept"
                        ]
                    cleaned_units.append(cleaned_unit)
            
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
            # Find relevant citations
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
    ) -> List[Dict[str, Any]]:
        """Generate simple atomic units as fallback."""
        units = []
        for concept in concept_names[:8]:
            # Map citations to concept
            relevant_citations = [
                c for c in citations[:5]
                if concept.lower() in c.get("title", "").lower()
            ]
            if not relevant_citations:
                relevant_citations = citations[:2] if citations else []
            
            key_resources = []
            for cit in relevant_citations[:3]:
                key_resources.append({
                    "type": cit.get("source_type", "web"),
                    "title": cit.get("title", "")[:80],
                    "url": cit.get("url", "")
                })
            
            units.append({
                "name": concept,
                "why_it_matters": f"{concept} is an important concept to understand.",
                "core_ideas": [
                    f"Understanding {concept}",
                    f"Applications of {concept}",
                    f"Key principles"
                ],
                "key_resources": key_resources,
                "deep_dive_resources": [],
                "checkpoints": [
                    "I can explain this without notes",
                    "I know when to use this concept"
                ]
            })
        return units
    
    def _group_units_into_phases(
        self,
        atomic_units: List[Dict[str, Any]],
        citations: List[Dict[str, Any]],
        answer_text: str
    ) -> List[Dict[str, Any]]:
        """
        Group atomic learning units into logical phases using LLM.
        
        Args:
            atomic_units: List of atomic learning unit dicts
            citations: List of citations
            answer_text: Generated answer/summary
        
        Returns:
            List of phase dicts
        """
        units_summary = "\n".join([
            f"{i+1}. {unit['name']}: {unit['why_it_matters'][:100]}"
            for i, unit in enumerate(atomic_units)
        ])
        
        # Count resources by type
        arxiv_count = sum(1 for c in citations if c.get("source_type") == "arxiv")
        youtube_count = sum(1 for c in citations if c.get("source_type") == "youtube")
        github_count = sum(1 for c in citations if c.get("source_type") == "github")
        web_count = sum(1 for c in citations if c.get("source_type") == "web")
        
        prompt = f"""Group the following learning units into logical phases (Phase 0, Phase 1, Phase 2, etc.).
Each phase should represent a coherent learning stage with a time estimate.

Learning Units:
{units_summary}

Resource Summary:
- ArXiv papers: {arxiv_count}
- YouTube videos: {youtube_count}
- GitHub repos: {github_count}
- Web articles: {web_count}

Guidelines:
- Phase 0: Prerequisites (foundational concepts, ½–1 day)
- Phase 1: Core Foundations (main concepts, 2–3 days)
- Phase 2: Advanced Topics (more complex concepts, 3–4 days)
- Phase 3: Specialized/Current Topics (cutting-edge, 2–3 days)
- Phase 4: Open Problems (if applicable, ongoing)

For each phase, provide:
- phase_number: 0, 1, 2, etc.
- name: Phase name (e.g., "Prerequisites", "Core Foundations")
- time_estimate: Time estimate (e.g., "½–1 day", "2–3 days")
- topic_names: List of unit names that belong to this phase

Format as JSON array. Create 3-5 phases total."""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            response_text = response.content.strip()
            
            # Extract JSON array
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                phase_data = json.loads(json_match.group(0))
            else:
                return self._fallback_phases(citations, atomic_units)
            
            # Map units to phases
            phases = []
            unit_map = {unit["name"]: unit for unit in atomic_units}
            
            for phase_info in phase_data:
                topic_names = phase_info.get("topic_names", [])
                phase_units = [unit_map[name] for name in topic_names if name in unit_map]
                
                if phase_units:
                    phases.append({
                        "phase_number": phase_info.get("phase_number", len(phases)),
                        "name": phase_info.get("name", f"Phase {len(phases)}"),
                        "time_estimate": phase_info.get("time_estimate", "2-3 days"),
                        "topics": phase_units,
                        "phase_checkpoint": f"☐ I completed Phase {phase_info.get('phase_number', len(phases))}"
                    })
            
            return phases if phases else self._fallback_phases(citations, atomic_units)
        except Exception as e:
            logger.warning(f"Failed to group units into phases: {e}")
            return self._fallback_phases(citations, atomic_units)
    
    def _fallback_phases(
        self,
        citations: List[Dict[str, Any]],
        atomic_units: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Generate simple phases as fallback."""
        if atomic_units is None:
            atomic_units = self._fallback_atomic_units(
                self._extract_key_concepts_flat(citations, {}),
                citations
            )
        
        if not atomic_units:
            return [{
                "phase_number": 0,
                "name": "Getting Started",
                "time_estimate": "1-2 days",
                "topics": [],
                "phase_checkpoint": "☐ I completed Phase 0"
            }]
        
        # Simple grouping: split into 2-3 phases
        num_phases = min(3, max(2, len(atomic_units) // 3 + 1))
        units_per_phase = len(atomic_units) // num_phases
        
        phases = []
        phase_names = ["Prerequisites", "Core Foundations", "Advanced Topics"]
        
        for i in range(num_phases):
            start_idx = i * units_per_phase
            end_idx = start_idx + units_per_phase if i < num_phases - 1 else len(atomic_units)
            phase_units = atomic_units[start_idx:end_idx]
            
            if phase_units:
                phases.append({
                    "phase_number": i,
                    "name": phase_names[i] if i < len(phase_names) else f"Phase {i}",
                    "time_estimate": "2-3 days" if i > 0 else "½–1 day",
                    "topics": phase_units,
                    "phase_checkpoint": f"☐ I completed Phase {i}"
                })
        
        return phases if phases else [{
            "phase_number": 0,
            "name": "Learning Topics",
            "time_estimate": "2-3 days",
            "topics": atomic_units,
            "phase_checkpoint": "☐ I completed Phase 0"
        }]
    
    def _organize_resources_by_source(
        self,
        citations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Organize citations by source type (already done, just return).
        
        Args:
            citations: List of citations
        
        Returns:
            List of citations (organized)
        """
        return citations
    
    def _create_timeline(
        self,
        citations: List[Dict[str, Any]],
        learning_objectives: List[str]
    ) -> List[str]:
        """
        Generate suggested timeline for studying using LLM.
        
        Args:
            citations: List of citations
            learning_objectives: List of learning objectives
        
        Returns:
            List of timeline item strings
        """
        if not citations:
            return ["Week 1: Review research materials (~2 hours)"]
        
        # Count resources by type
        arxiv_count = sum(1 for c in citations if c.get("source_type") == "arxiv")
        youtube_count = sum(1 for c in citations if c.get("source_type") == "youtube")
        github_count = sum(1 for c in citations if c.get("source_type") == "github")
        web_count = sum(1 for c in citations if c.get("source_type") == "web")
        
        resource_summary = f"""
Resources available:
- ArXiv papers: {arxiv_count}
- YouTube videos: {youtube_count}
- GitHub repositories: {github_count}
- Web articles: {web_count}
Total: {len(citations)} resources
"""
        
        objectives_text = "\n".join([f"- {obj}" for obj in learning_objectives[:5]])
        
        prompt = f"""Create a realistic week-by-week study timeline based on the following resources and learning objectives.

{resource_summary}

Learning Objectives:
{objectives_text}

Guidelines:
- Estimate realistic time per resource type:
  * ArXiv papers: ~2 hours each (reading + understanding)
  * YouTube videos: ~1 hour each (watching + taking notes)
  * GitHub repos: ~2 hours each (exploring + understanding code)
  * Web articles: ~1 hour each (reading + note-taking)
- Organize by priority: foundational papers first, then videos/tutorials, then code exploration
- Group similar resources together in the same week
- Keep each week's workload reasonable (4-8 hours total)
- Format as: "Week X: [Activity] ([resource count] [type], ~[hours] hours)"

Generate 2-4 weeks of timeline items. Be realistic about time estimates."""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            timeline_text = response.content.strip()
            
            # Parse timeline items
            timeline = []
            for line in timeline_text.split("\n"):
                line = line.strip()
                # Remove week markers if present
                for marker in ["-", "•", "*"]:
                    if line.startswith(marker):
                        line = line[len(marker):].strip()
                # Look for "Week" pattern
                if "week" in line.lower() or "day" in line.lower() or line:
                    if line:
                        timeline.append(line)
            
            # Fallback if parsing fails
            if not timeline:
                return self._fallback_timeline(citations)
            
            return timeline[:4]  # Limit to 4 weeks
        except Exception as e:
            logger.warning(f"Failed to generate timeline with LLM: {e}")
            return self._fallback_timeline(citations)
    
    def _fallback_timeline(self, citations: List[Dict[str, Any]]) -> List[str]:
        """Fallback timeline generation using simple heuristics."""
        timeline = []
        
        arxiv_count = sum(1 for c in citations if c.get("source_type") == "arxiv")
        youtube_count = sum(1 for c in citations if c.get("source_type") == "youtube")
        github_count = sum(1 for c in citations if c.get("source_type") == "github")
        web_count = sum(1 for c in citations if c.get("source_type") == "web")
        
        week = 1
        if arxiv_count > 0:
            timeline.append(f"Week {week}: Read foundational papers ({arxiv_count} paper(s), ~{arxiv_count * 2} hours)")
            week += 1
        if youtube_count > 0:
            timeline.append(f"Week {week}: Watch video tutorials ({youtube_count} video(s), ~{youtube_count * 1} hours)")
            week += 1
        if github_count > 0:
            timeline.append(f"Week {week}: Explore code implementations ({github_count} repo(s), ~{github_count * 2} hours)")
            week += 1
        if web_count > 0:
            timeline.append(f"Week {week}: Review articles and documentation ({web_count} article(s), ~{web_count * 1} hours)")
            week += 1
        
        if not timeline:
            total_resources = len(citations)
            timeline.append(f"Week 1: Review all resources ({total_resources} resource(s), ~{total_resources * 1.5} hours)")
        
        return timeline
    
    def _create_next_steps(
        self,
        citations: List[Dict[str, Any]],
        learning_objectives: List[str]
    ) -> List[str]:
        """
        Generate next steps/action items using LLM.
        
        Args:
            citations: List of citations
            learning_objectives: List of learning objectives
        
        Returns:
            List of next step strings
        """
        if not citations:
            return [
                "Review all collected resources",
                "Take notes on key concepts",
                "Practice with examples or exercises"
            ]
        
        # Get top resources by type
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
        
        prompt = f"""Based on the following learning objectives and top resources, create 4-6 actionable next steps.

Learning Objectives:
{objectives_text}

Top Resources:
{resources_text}

Create specific, actionable next steps that:
- Reference specific resources by name (truncate long titles)
- Are concrete and achievable
- Follow a logical learning progression
- Include a mix of reading, watching, and hands-on activities

Format as a bulleted list, one step per line. Start each step with an action verb (Read, Watch, Explore, Review, Practice, etc.)."""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            steps_text = response.content.strip()
            
            # Parse steps
            steps = []
            for line in steps_text.split("\n"):
                line = line.strip()
                # Remove bullet markers
                for marker in ["-", "•", "*", "1.", "2.", "3.", "4.", "5.", "6."]:
                    if line.startswith(marker):
                        line = line[len(marker):].strip()
                if line and len(line) > 5:
                    steps.append(line)
            
            # Fallback if parsing fails
            if not steps:
                return self._fallback_next_steps(citations)
            
            return steps[:6]  # Limit to 6 steps
        except Exception as e:
            logger.warning(f"Failed to generate next steps with LLM: {e}")
            return self._fallback_next_steps(citations)
    
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

