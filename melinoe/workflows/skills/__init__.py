"""Public API for all workflow skills and their result dataclasses."""

from melinoe.workflows.skills.book_lookup import BookLookupSkill
from melinoe.workflows.skills.book_lookup import BookMetadata
from melinoe.workflows.skills.cover_analyzer import CoverAnalysis
from melinoe.workflows.skills.cover_analyzer import CoverAnalyzerSkill
from melinoe.workflows.skills.enrich_professor_profile import EnrichProfessorProfileSkill
from melinoe.workflows.skills.enrich_professor_profile import ProfileEnrichmentResult
from melinoe.workflows.skills.execute_web_mentions import ExecuteWebMentionsSkill
from melinoe.workflows.skills.execute_web_mentions import WebMention
from melinoe.workflows.skills.execute_web_mentions import WebMentionsResult
from melinoe.workflows.skills.hecate import BookCoverCheck
from melinoe.workflows.skills.hecate import HecateSkill
from melinoe.workflows.skills.load_relevant_memory import LoadRelevantMemorySkill
from melinoe.workflows.skills.load_relevant_memory import RelevantMemories
from melinoe.workflows.skills.load_scraping_state import LoadScrapingStateSkill
from melinoe.workflows.skills.load_scraping_state import ScrapingState
from melinoe.workflows.skills.loader import Definition
from melinoe.workflows.skills.loader import load_agent
from melinoe.workflows.skills.loader import load_skill
from melinoe.workflows.skills.loader import load_soul
from melinoe.workflows.skills.plan_scraping import PlanScrapingSkill
from melinoe.workflows.skills.plan_scraping import ScrapingPlan
from melinoe.workflows.skills.professor_cataloger import ProfessorCatalogerSkill
from melinoe.workflows.skills.professor_cataloger import ProfessorWorkMetadata
from melinoe.workflows.skills.professor_classifier import ProfessorClassifierSkill
from melinoe.workflows.skills.professor_classifier import ProfessorWorkClassification
from melinoe.workflows.skills.professor_detector import ProfessorDetectionResult
from melinoe.workflows.skills.professor_detector import ProfessorDetectorSkill
from melinoe.workflows.skills.save_scraping_state import SavedScrapingState
from melinoe.workflows.skills.save_scraping_state import SaveScrapingStateSkill
from melinoe.workflows.skills.title_page_analyzer import CipData
from melinoe.workflows.skills.title_page_analyzer import TitlePageAnalysis
from melinoe.workflows.skills.title_page_analyzer import TitlePageAnalyzerSkill
from melinoe.workflows.skills.write_memory import WriteMemorySkill
from melinoe.workflows.skills.write_memory import WrittenMemory
from melinoe.workflows.skills.write_professor_memory import WriteProfessorMemorySkill
from melinoe.workflows.skills.write_professor_memory import WrittenProfessorMemory

__all__ = [
    "BookCoverCheck",
    "BookLookupSkill",
    "BookMetadata",
    "CipData",
    "CoverAnalysis",
    "CoverAnalyzerSkill",
    "Definition",
    "EnrichProfessorProfileSkill",
    "ExecuteWebMentionsSkill",
    "HecateSkill",
    "LoadRelevantMemorySkill",
    "LoadScrapingStateSkill",
    "PlanScrapingSkill",
    "ProfessorCatalogerSkill",
    "ProfessorClassifierSkill",
    "ProfessorDetectionResult",
    "ProfessorDetectorSkill",
    "ProfessorWorkClassification",
    "ProfessorWorkMetadata",
    "ProfileEnrichmentResult",
    "RelevantMemories",
    "SaveScrapingStateSkill",
    "SavedScrapingState",
    "ScrapingPlan",
    "ScrapingState",
    "TitlePageAnalysis",
    "TitlePageAnalyzerSkill",
    "WebMention",
    "WebMentionsResult",
    "WriteMemorySkill",
    "WriteProfessorMemorySkill",
    "WrittenMemory",
    "WrittenProfessorMemory",
    "load_agent",
    "load_skill",
    "load_soul",
]
