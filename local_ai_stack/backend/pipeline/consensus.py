"""Mécanisme consensus PLAN ↔ PLAN-REVIEW (Plan 5C Task 6).

Orchestration de 2 rounds max entre Stage4aPlan (R1) et Stage4bPlanReview
(Pro). Trois résolutions possibles :

1. ``approve`` → on garde le plan tel quel.
2. ``revise`` → on prend ``merged_plan`` du reviewer.
3. ``reject`` + 2 rounds rouges → deadlock, on remet la décision à
   l'utilisateur (UI modal).

Events WS émis :
- ``consensus_round`` à chaque round avec ``{round, verdict, plan_summary}``.
- ``consensus_disagreement`` si deadlock après ``max_rounds``.
"""
import json
from dataclasses import dataclass, field
from typing import Optional

from backend.models import WSEvent
from backend.pipeline.stage_4a_plan import PlanResult, Stage4aPlan
from backend.pipeline.stage_4b_plan_review import PlanReview, Stage4bPlanReview
from backend.pipeline.types import PipelineContext


_DEFAULT_MAX_ROUNDS = 2


@dataclass
class PlanConsensusResult:
    """Output du consensus 2/2."""

    plan: Optional[PlanResult] = None
    rounds: int = 0
    deadlock: bool = False
    # Si deadlock : tous les plans produits, l'utilisateur choisit.
    plans: list[PlanResult] = field(default_factory=list)
    reviews: list[PlanReview] = field(default_factory=list)


async def run_plan_consensus(
    llm_manager,
    ws_streamer,
    ctx: PipelineContext,
    max_rounds: int = _DEFAULT_MAX_ROUNDS,
) -> PlanConsensusResult:
    """Boucle Stage4aPlan → Stage4bPlanReview jusqu'à ``max_rounds``."""
    plans: list[PlanResult] = []
    reviews: list[PlanReview] = []

    last_reject_concerns: list[str] = []

    for round_idx in range(1, max_rounds + 1):
        # Injection des concerns du round précédent dans retry_context pour
        # que Stage4aPlan voie les raisons du reject.
        if last_reject_concerns:
            ctx.retry_context = {
                "previous_review_concerns": list(last_reject_concerns),
                "round": round_idx,
            }
        else:
            ctx.retry_context = None

        plan_sr = await Stage4aPlan(llm_manager, ws_streamer).run(ctx)
        if not plan_sr.success or plan_sr.output is None:
            # Échec dur de Stage4a → on s'arrête en deadlock vide.
            return PlanConsensusResult(
                plan=None,
                rounds=round_idx,
                deadlock=True,
                plans=plans,
                reviews=reviews,
            )
        plan: PlanResult = plan_sr.output
        plans.append(plan)

        review_sr = await Stage4bPlanReview(llm_manager, ws_streamer).run(ctx)
        if not review_sr.success or review_sr.output is None:
            return PlanConsensusResult(
                plan=plan,  # On garde au moins le plan R1 si la review crashe.
                rounds=round_idx,
                deadlock=False,
                plans=plans,
                reviews=reviews,
            )
        review: PlanReview = review_sr.output
        reviews.append(review)

        await _emit_round(ws_streamer, ctx, round_idx, review, plan)

        if review.verdict == "approve":
            ctx.retry_context = None
            return PlanConsensusResult(
                plan=plan, rounds=round_idx, deadlock=False,
                plans=plans, reviews=reviews,
            )

        if review.verdict == "revise" and review.merged_plan is not None:
            ctx.retry_context = None
            return PlanConsensusResult(
                plan=review.merged_plan,
                rounds=round_idx,
                deadlock=False,
                plans=plans,
                reviews=reviews,
            )

        # reject (ou revise sans merged_plan) → on prépare le round suivant.
        last_reject_concerns = list(review.concerns or [])

    # max_rounds épuisés sans consensus → deadlock.
    await _emit_disagreement(ws_streamer, ctx, plans)
    ctx.retry_context = None
    return PlanConsensusResult(
        plan=None,
        rounds=max_rounds,
        deadlock=True,
        plans=plans,
        reviews=reviews,
    )


# ── Events WS ────────────────────────────────────────────────────────────────


async def _emit_round(
    ws_streamer, ctx: PipelineContext, round_idx: int,
    review: PlanReview, plan: PlanResult,
) -> None:
    if ws_streamer is None:
        return
    summary = {
        "changes_count": len(plan.changes),
        "tests_count": len(plan.tests_to_run),
        "estimated_risk": plan.estimated_risk,
    }
    await ws_streamer.broadcast(WSEvent(
        type="consensus_round",
        data={
            "round": round_idx,
            "verdict": review.verdict,
            "plan_summary": summary,
            "concerns": review.concerns[:5],
        },
        session_id=ctx.session_id,
    ))


async def _emit_disagreement(
    ws_streamer, ctx: PipelineContext, plans: list[PlanResult],
) -> None:
    if ws_streamer is None:
        return
    plans_summary = [
        {
            "changes": [
                {"file": c.file, "operation": c.operation, "description": c.description}
                for c in p.changes
            ],
            "tests_to_run": p.tests_to_run,
            "estimated_risk": p.estimated_risk,
            "rationale": p.rationale[:300],
        }
        for p in plans
    ]
    await ws_streamer.broadcast(WSEvent(
        type="consensus_disagreement",
        data={"plans": plans_summary},
        session_id=ctx.session_id,
    ))


def serialize_plan_for_memory(plan: PlanResult) -> str:
    """Helper pour persister un plan en str dans LongTermMemory.llm_messages."""
    return json.dumps(
        {
            "changes": [
                {
                    "file": c.file,
                    "operation": c.operation,
                    "description": c.description,
                }
                for c in plan.changes
            ],
            "tests_to_run": plan.tests_to_run,
            "estimated_risk": plan.estimated_risk,
            "complexity_confirm": plan.complexity_confirm,
        },
        ensure_ascii=False,
    )[:2000]
