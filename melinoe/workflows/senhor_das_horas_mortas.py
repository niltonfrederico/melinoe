"""SenhorDasHorasMortasWorkflow: scraper autônomo que rastreia menções a Nilton Manoel na web."""

import re
import uuid
from dataclasses import asdict
from datetime import UTC
from datetime import datetime
from typing import Any

from melinoe.logger import workflow_log
from melinoe.workflows.base import Step
from melinoe.workflows.base import Workflow
from melinoe.workflows.kardo_navalha import KardoNavalhaWorkflow
from melinoe.workflows.kardo_navalha import ProfessorWorkAlreadyRegisteredError
from melinoe.workflows.skills.enrich_professor_profile import EnrichProfessorProfileSkill
from melinoe.workflows.skills.execute_web_mentions import ExecuteWebMentionsSkill
from melinoe.workflows.skills.execute_web_mentions import WebMention
from melinoe.workflows.skills.load_scraping_state import LoadScrapingStateSkill
from melinoe.workflows.skills.loader import load_agent
from melinoe.workflows.skills.loader import load_soul
from melinoe.workflows.skills.plan_scraping import PlanScrapingSkill
from melinoe.workflows.skills.save_scraping_state import SaveScrapingStateSkill


class SenhorDasHorasMortasWorkflow(Workflow):
    agent = "senhor_das_horas_mortas"

    def __init__(self) -> None:
        self._agent_def = load_agent("senhor_das_horas_mortas")
        self._soul_def = load_soul("senhor_das_horas_mortas")
        self._load_state = LoadScrapingStateSkill()
        self._plan = PlanScrapingSkill()
        self._execute = ExecuteWebMentionsSkill()
        self._enrich = EnrichProfessorProfileSkill()
        self._save_state = SaveScrapingStateSkill()
        self.steps: list[Step] = [
            self._load_state,
            self._plan,
            self._execute,
            self._enrich,
            self._save_state,
        ]
        super().__init__()

    @property
    def system_prompt(self) -> str:
        return f"{self._soul_def.system_prompt}\n\n---\n\n{self._agent_def.system_prompt}"

    def run(self, trigger: str = "cron", batch_size: int = 10) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        workflow_log.info("SenhorDasHorasMortasWorkflow → session=%s, trigger=%s", session_id, trigger)

        self._emit("Carregando estado anterior...")
        state = self._load_state.run()
        workflow_log.info(
            "State loaded: visited=%s, pending=%s, mentions=%s, session=%s",
            len(state.visited_urls),
            len(state.pending_urls),
            len(state.found_mentions),
            state.session_count,
        )

        # Stop if more than 24 h have passed since the last new mention AND the pending queue is empty.
        # This means the daily cron ran, found nothing new, and there is nowhere left to look.
        if not state.pending_urls and state.last_new_mention_at:
            delta = datetime.now(tz=UTC) - datetime.fromisoformat(state.last_new_mention_at)
            if delta.total_seconds() >= 86400:
                workflow_log.info("No pending URLs and no new mention in the last 24 h — cataloging appears complete.")
                return {
                    "session_id": session_id,
                    "urls_visited": 0,
                    "new_mentions_found": 0,
                    "profile_enriched": False,
                    "pending_urls_remaining": 0,
                    "summary": "Sem novos resultados há mais de 24 h. Catalogação possivelmente concluída.",
                }

        total_visited = 0
        total_mentions = 0
        total_works_saved = 0
        profile_enriched = False
        all_discoveries: list[str] = []
        iteration = 0

        while True:
            iteration += 1
            workflow_log.info("Loop iteration %s: pending=%s", iteration, len(state.pending_urls))

            self._emit(f"Planejando rota de pesquisa (iteração {iteration})...")
            plan = self._plan.run(state=state, trigger=trigger, batch_size=batch_size)
            workflow_log.info("Plan ready: %s URLs, %s queries", len(plan.next_urls), len(plan.search_queries))
            if plan.planning_notes:
                workflow_log.info("Planning notes: %s", plan.planning_notes)

            if not plan.next_urls and not plan.search_queries:
                workflow_log.info("No new URLs or queries — stopping loop")
                break

            self._emit(f"Rastreando {len(plan.next_urls)} endereços...")
            mentions_result = self._execute.run(plan=plan, state=state)
            workflow_log.info(
                "Scraping done: visited=%s, failed=%s, mentions=%s, discovered=%s",
                len(mentions_result.urls_visited),
                len(mentions_result.urls_failed),
                len(mentions_result.mentions),
                len(mentions_result.newly_discovered_urls),
            )

            self._emit("Atualizando perfil do Professor...")
            enrichment = self._enrich.run(mentions_result=mentions_result)
            if enrichment.profile_updated:
                profile_enriched = True
                workflow_log.info("Profile enriched: %s new discoveries", len(enrichment.new_discoveries))
                for discovery in enrichment.new_discoveries:
                    workflow_log.info("  ↳ %s", discovery)

            works_saved = self._catalog_found_works(mentions_result.mentions)
            if works_saved:
                workflow_log.info("Works cataloged this iteration: %s", works_saved)
                total_works_saved += works_saved

            self._emit("Salvando progresso...")
            saved = self._save_state.run(state=state, mentions_result=mentions_result)
            workflow_log.info(
                "State saved: total_visited=%s, total_pending=%s, total_mentions=%s",
                saved.total_visited,
                saved.total_pending,
                saved.total_mentions,
            )

            total_visited += len(mentions_result.urls_visited)
            total_mentions += len(mentions_result.mentions)
            all_discoveries.extend(mentions_result.newly_discovered_urls)

            # Reload state from disk so the next iteration sees the updated pending queue
            state = self._load_state.run()

            # Stop when there is nothing left to visit and DDG found no new URLs this iteration
            if not state.pending_urls and not mentions_result.newly_discovered_urls:
                workflow_log.info("Pending queue empty and no new discoveries — stopping loop")
                break

        result: dict[str, Any] = {
            "session_id": session_id,
            "urls_visited": total_visited,
            "new_mentions_found": total_mentions,
            "works_saved": total_works_saved,
            "profile_enriched": profile_enriched,
            "new_discoveries": list(dict.fromkeys(all_discoveries)),
            "pending_urls_remaining": len(state.pending_urls),
            "summary": self._build_summary(total_visited, total_mentions, total_works_saved, profile_enriched),
        }

        workflow_log.info("SenhorDasHorasMortasWorkflow complete → session=%s", session_id)
        return result

    _BYLINE_PATTERNS = re.compile(
        r"e-mail\s*:|@|\bpor\s*:\s*\w|\bcoluna\b|\bcolunista\b|\bredação\b|\bredacao\b",
        re.IGNORECASE,
    )

    def _catalog_found_works(self, mentions: list[WebMention]) -> int:
        saved = 0
        for mention in mentions:
            if mention.confidence not in ("high", "medium"):
                continue
            snippet = mention.snippet or ""
            if len(snippet) < 30:
                continue
            if self._BYLINE_PATTERNS.search(snippet):
                workflow_log.debug("Skipping byline/metadata snippet from %s", mention.url)
                continue

            try:
                wf = KardoNavalhaWorkflow()
                wf.run(
                    work_text=snippet,
                    mention_metadata=asdict(mention),
                )
                saved += 1
                workflow_log.info("Work cataloged from %s", mention.url)
            except ProfessorWorkAlreadyRegisteredError:
                workflow_log.debug("Work already registered — skipping %s", mention.url)
            except Exception as exc:
                workflow_log.warning("Failed to catalog work from %s — %s", mention.url, exc)
        return saved

    def _build_summary(self, urls_visited: int, new_mentions: int, works_saved: int, profile_enriched: bool) -> str:
        parts: list[str] = []
        if new_mentions:
            parts.append(f"{new_mentions} menção(ões) encontrada(s)")
        if works_saved:
            parts.append(f"{works_saved} obra(s) catalogada(s)")
        if profile_enriched:
            parts.append("perfil atualizado")
        parts.append(f"{urls_visited} URL(s) visitada(s)")
        return "; ".join(parts) if parts else "Sessão concluída sem novas descobertas."
