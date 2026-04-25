#!/usr/bin/env python3
"""Feed manual information about Nilton Manoel directly into the professor profile enrichment pipeline.

Usage examples:

    # Pipe text directly
    echo "Nilton Manoel foi homenageado na Câmara Municipal em 2003." | poetry run python scripts/enrich_professor.py

    # Read from a text file
    poetry run python scripts/enrich_professor.py notas.txt

    # Interactive multiline input (Ctrl+D to finish)
    poetry run python scripts/enrich_professor.py

    # Tag the source
    poetry run python scripts/enrich_professor.py --source "depoimento_familiar" notas.txt
"""

import argparse
import sys

from melinoe.workflows.skills.enrich_professor_profile import EnrichProfessorProfileSkill
from melinoe.workflows.skills.execute_web_mentions import WebMention
from melinoe.workflows.skills.execute_web_mentions import WebMentionsResult


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich the professor profile with manually provided information about Nilton Manoel.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "file",
        nargs="?",
        type=argparse.FileType("r"),
        default=None,
        help="Text file with information. Omit to read from stdin.",
    )
    parser.add_argument(
        "--source",
        default="family_memory",
        help="Label for the information source, e.g. 'family_memory', 'depoimento_familiar' (default: family_memory)",
    )
    parser.add_argument(
        "--url",
        default="manual://family-input",
        help="Optional URL or identifier to associate with this information (default: manual://family-input)",
    )
    args = parser.parse_args()

    if args.file is not None:
        text = args.file.read().strip()
    else:
        if sys.stdin.isatty():
            print("Enter information about Nilton Manoel (Ctrl+D when done):", file=sys.stderr)
        text = sys.stdin.read().strip()

    if not text:
        parser.error("No input text provided.")

    mention = WebMention(
        url=args.url,
        snippet=text,
        confidence="high",
        source_type=args.source,
        discovered_aliases=[],
        discovered_venues=[],
        discovered_years=[],
        context_notes="Provided manually by family member — treat as high-confidence primary source.",
        article_text=text,
    )
    mentions_result = WebMentionsResult(
        mentions=[mention],
        newly_discovered_urls=[],
        urls_visited=[args.url],
        urls_failed=[],
    )

    skill = EnrichProfessorProfileSkill()
    result = skill.run(mentions_result=mentions_result)

    if result.profile_updated:
        print("Profile updated successfully.")
        for discovery in result.new_discoveries:
            print(f"  + {discovery}")
    else:
        print("No changes made to profile (information may already be present or nothing new was found).")


if __name__ == "__main__":
    main()
