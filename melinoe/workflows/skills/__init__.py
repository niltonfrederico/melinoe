"""Public API for all workflow skills and their result dataclasses."""

from melinoe.workflows.skills.book_lookup import BookLookupSkill
from melinoe.workflows.skills.book_lookup import BookMetadata
from melinoe.workflows.skills.cover_analyzer import CoverAnalysis
from melinoe.workflows.skills.cover_analyzer import CoverAnalyzerSkill
from melinoe.workflows.skills.hecate import BookCoverCheck
from melinoe.workflows.skills.hecate import HecateSkill
from melinoe.workflows.skills.load_relevant_memory import LoadRelevantMemorySkill
from melinoe.workflows.skills.load_relevant_memory import RelevantMemories
from melinoe.workflows.skills.loader import Definition
from melinoe.workflows.skills.loader import load_agent
from melinoe.workflows.skills.loader import load_skill
from melinoe.workflows.skills.loader import load_soul
from melinoe.workflows.skills.title_page_analyzer import CipData
from melinoe.workflows.skills.title_page_analyzer import TitlePageAnalysis
from melinoe.workflows.skills.title_page_analyzer import TitlePageAnalyzerSkill
from melinoe.workflows.skills.write_memory import WriteMemorySkill
from melinoe.workflows.skills.write_memory import WrittenMemory

__all__ = [
    "BookCoverCheck",
    "BookLookupSkill",
    "BookMetadata",
    "CipData",
    "CoverAnalysis",
    "CoverAnalyzerSkill",
    "Definition",
    "HecateSkill",
    "LoadRelevantMemorySkill",
    "RelevantMemories",
    "TitlePageAnalysis",
    "TitlePageAnalyzerSkill",
    "WriteMemorySkill",
    "WrittenMemory",
    "load_agent",
    "load_skill",
    "load_soul",
]
