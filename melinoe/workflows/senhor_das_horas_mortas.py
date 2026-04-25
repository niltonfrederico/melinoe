"""SenhorDasHorasMortasWorkflow: scraper autônomo que rastreia menções a Nilton Manoel na web."""

import uuid
from typing import Any

from melinoe.logger import workflow_log
from melinoe.workflows.base import Step
from melinoe.workflows.base import Workflow
from melinoe.workflows.skills.enrich_professor_profile import EnrichProfessorProfileSkill
from melinoe.workflows.skills.execute_web_mentions import ExecuteWebMentionsSkill
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

    def run(self, trigger: str = "cron", batch_size: int = 10, **kwargs: Any) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        workflow_log.info(f"SenhorDasHorasMortasWorkflow → session={session_id}, trigger={trigger}")

        self._emit("Carregando estado anterior...")
        state = self._load_state.run()
        workflow_log.info(
            f"State loaded: visited={len(state.visited_urls)}, "
            f"pending={len(state.pending_urls)}, "
            f"mentions={len(state.found_mentions)}, "
            f"session={state.session_count}"
        )

        self._emit("Planejando próxima rota de pesquisa...")
        plan = self._plan.run(state=state, trigger=trigger, batch_size=batch_size)
        workflow_log.info(f"Plan ready: {len(plan.next_urls)} URLs, {len(plan.search_queries)} queries")
        if plan.planning_notes:
            workflow_log.info(f"Planning notes: {plan.planning_notes}")

        if not plan.next_urls:
            workflow_log.info("No new URLs to visit — session complete")
            return {
                "session_id": session_id,
                "urls_visited": 0,
                "new_mentions_found": 0,
                "profile_enriched": False,
                "pending_urls_remaining": len(state.pending_urls),
                "summary": "Nenhuma URL nova para visitar nesta sessão.",
            }

        self._emit(f"Rastreando {len(plan.next_urls)} endereços...")
        mentions_result = self._execute.run(plan=plan, state=state)
        workflow_log.info(
            f"Scraping done: visited={len(mentions_result.urls_visited)}, "
            f"failed={len(mentions_result.urls_failed)}, "
            f"mentions={len(mentions_result.mentions)}, "
            f"discovered={len(mentions_result.newly_discovered_urls)}"
        )

        self._emit("Atualizando perfil do Professor...")
        enrichment = self._enrich.run(mentions_result=mentions_result)
        if enrichment.profile_updated:
            workflow_log.info(f"Profile enriched: {len(enrichment.new_discoveries)} new discoveries")
            for discovery in enrichment.new_discoveries:
                workflow_log.info(f"  ↳ {discovery}")

        self._emit("Salvando progresso...")
        saved = self._save_state.run(state=state, mentions_result=mentions_result)
        workflow_log.info(
            f"State saved: total_visited={saved.total_visited}, "
            f"total_pending={saved.total_pending}, "
            f"total_mentions={saved.total_mentions}"
        )

        result: dict[str, Any] = {
            "session_id": session_id,
            "urls_visited": len(mentions_result.urls_visited),
            "new_mentions_found": len(mentions_result.mentions),
            "profile_enriched": enrichment.profile_updated,
            "new_discoveries": enrichment.new_discoveries,
            "pending_urls_remaining": saved.total_pending,
            "summary": self._build_summary(mentions_result, enrichment),
        }

        workflow_log.info(f"SenhorDasHorasMortasWorkflow complete → session={session_id}")
        return result

    def _build_summary(self, mentions_result: Any, enrichment: Any) -> str:
        parts: list[str] = []
        if mentions_result.mentions:
            parts.append(f"{len(mentions_result.mentions)} menção(ões) encontrada(s)")
        if enrichment.profile_updated:
            parts.append(f"perfil atualizado com {len(enrichment.new_discoveries)} descoberta(s) nova(s)")
        if mentions_result.urls_failed:
            parts.append(f"{len(mentions_result.urls_failed)} URL(s) inacessível(is)")
        return "; ".join(parts) if parts else "Sessão concluída sem novas descobertas."
