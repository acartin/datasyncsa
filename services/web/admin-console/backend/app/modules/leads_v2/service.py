from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import text
from app.dal.database import engine
from app.config.settings import settings
from app.contracts.scoring_schema import ScoringSchemaV2, ScoringValuesV2, ScoreItemValueV2


class LeadsV2Service:
    async def get_client_vertical_context(self, client_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Resolve tenant scoring context from lead_clients (vertical + scoring_model_id).
        """
        query_str = text(
            """
            SELECT
                c.id AS client_id,
                c.vertical_id AS vertical_id,
                c.scoring_model_id AS scoring_model_id,
                v.slug AS vertical_slug,
                v.name AS vertical_name
            FROM lead_clients c
            LEFT JOIN lead_client_verticals v ON v.id = c.vertical_id
            WHERE c.id = :client_id
            """
        )
        async with engine.connect() as conn:
            result = await conn.execute(query_str, {"client_id": client_id})
            row = result.mappings().first()
            if not row:
                return None
            return dict(row)

    async def get_my_leads_with_scoring_v2(
        self,
        user_id: UUID,
        is_superuser: bool = False,
        tenant_ids: Optional[List[UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch leads with dynamic scoring v2 (using lead_scorecards/items).
        Returns list of leads with latest scorecard data.
        """
        # First check if scoring v2 is enabled
        if not settings.scoring_v2_enabled:
            return await self._fallback_to_legacy(
                user_id=user_id,
                is_superuser=is_superuser,
                tenant_ids=tenant_ids,
            )

        access_filter = ""
        params: Dict[str, Any] = {"uid": user_id}
        if not is_superuser:
            if tenant_ids:
                access_filter = " AND (l.assigned_user_id = :uid OR l.client_id = ANY(:tenant_ids))"
                params["tenant_ids"] = tenant_ids
            else:
                access_filter = " AND l.assigned_user_id = :uid"

        query_str = text("""
            WITH latest_scorecards AS (
                SELECT 
                    sc.lead_id,
                    sc.id as scorecard_id,
                    sc.score_total,
                    sc.priority_label,
                    sc.reasoning,
                    sc.created_at,
                    sc.model_id,
                    sc.model_version,
                    sc.prompt_version,
                    ROW_NUMBER() OVER (PARTITION BY sc.lead_id ORDER BY sc.created_at DESC) as rn
                FROM lead_scorecards sc
                INNER JOIN lead_leads l ON l.id = sc.lead_id
                WHERE l.deleted_at IS NULL
                """ + access_filter + """
            ),
            score_items_agg AS (
                SELECT 
                    si.scorecard_id,
                    json_agg(
                        json_build_object(
                            'criterion_key', si.criterion_key,
                            'score', si.score,
                            'band_id', si.band_id,
                            'explanation', si.explanation
                        )
                    ) as items
                FROM lead_score_items si
                WHERE si.scorecard_id IN (SELECT scorecard_id FROM latest_scorecards WHERE rn = 1)
                GROUP BY si.scorecard_id
            )
            SELECT 
                l.id, l.full_name, l.email, l.phone, l.business_domain,
                l.created_at, l.status_id, l.client_id,
                ls.scorecard_id, ls.score_total, ls.priority_label, ls.reasoning,
                ls.created_at as scored_at, ls.model_id, ls.model_version, ls.prompt_version,
                COALESCE(sia.items, '[]'::json) as score_items,
                st.name as status_label, st.color as status_color, st.icon as status_icon
            FROM lead_leads l
            INNER JOIN latest_scorecards ls ON l.id = ls.lead_id AND ls.rn = 1
            LEFT JOIN score_items_agg sia ON ls.scorecard_id = sia.scorecard_id
            LEFT JOIN lead_statuses st ON l.status_id = st.id
            WHERE l.deleted_at IS NULL
            """ + access_filter + """
            ORDER BY ls.score_total DESC NULLS LAST, l.created_at DESC
        """)
        
        async with engine.connect() as conn:
            result = await conn.execute(query_str, params)
            rows = result.all()
            return [dict(row._mapping) for row in rows]
    
    async def _fallback_to_legacy(
        self,
        user_id: UUID,
        is_superuser: bool = False,
        tenant_ids: Optional[List[UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fallback to legacy scoring when v2 is not enabled.
        This maintains backward compatibility.
        """
        from app.modules.leads.service import service as legacy_service
        return await legacy_service.get_my_leads(
            user_id=user_id,
            is_superuser=is_superuser,
            tenant_ids=tenant_ids,
        )
    
    async def get_lead_detail_with_scoring_v2(
        self,
        lead_id: UUID,
        user_id: UUID,
        is_superuser: bool,
        tenant_ids: Optional[List[UUID]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed lead data with scoring v2 including score items.
        """
        # Check feature flags
        if not settings.scoring_v2_enabled and settings.legacy_scoring_read_compat:
            return await self._fallback_to_legacy_detail(lead_id, user_id, is_superuser, tenant_ids)
        
        # Build access filter
        access_filter = ""
        params = {"id": lead_id, "user_id": user_id}
        
        if not is_superuser:
            if tenant_ids:
                access_filter = " AND (l.assigned_user_id = :user_id OR l.client_id = ANY(:tenant_ids))"
                params["tenant_ids"] = tenant_ids
            else:
                access_filter = " AND l.assigned_user_id = :user_id"
        
        query_str = text(f"""
            WITH latest_scorecard AS (
                SELECT 
                    sc.*,
                    ROW_NUMBER() OVER (ORDER BY sc.created_at DESC) as rn
                FROM lead_scorecards sc
                WHERE sc.lead_id = :id
            ),
            score_items_detail AS (
                SELECT 
                    si.*,
                    lb.band_key, lb.label as band_label, lb.color as band_color, lb.icon as band_icon
                FROM lead_score_items si
                LEFT JOIN lead_scoring_bands lb ON si.band_id = lb.id
                WHERE si.scorecard_id = (SELECT id FROM latest_scorecard WHERE rn = 1)
            ),
            model_criteria AS (
                SELECT 
                    lsc.model_id,
                    json_agg(
                        json_build_object(
                            'criterion_key', lsc.criterion_key,
                            'label', lsc.label,
                            'weight', lsc.weight,
                            'min_score', lsc.min_score,
                            'max_score', lsc.max_score,
                            'display_order', lsc.display_order,
                            'is_active', lsc.is_active
                        )
                    ) as criteria
                FROM lead_scoring_criteria lsc
                WHERE lsc.model_id = (SELECT model_id FROM latest_scorecard WHERE rn = 1)
                AND lsc.is_active = true
                GROUP BY lsc.model_id
            )
            SELECT 
                l.*,
                ls.id as scorecard_id, ls.score_total, ls.priority_label, ls.reasoning,
                ls.model_id, ls.model_version, ls.prompt_version, ls.created_at as scored_at,
                ls.raw_payload,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'id', sid.id,
                            'criterion_key', sid.criterion_key,
                            'score', sid.score,
                            'band_key', sid.band_key,
                            'band_label', sid.band_label,
                            'band_color', sid.band_color,
                            'band_icon', sid.band_icon,
                            'explanation', sid.explanation,
                            'extracted_data', sid.extracted_data
                        )
                    ) FILTER (WHERE sid.id IS NOT NULL), '[]'::json
                ) as score_items_detail,
                COALESCE(mc.criteria, '[]'::json) as model_criteria,
                st.name as status_label, st.color as status_color, st.icon as status_icon,
                cp.name as cp_label, cp.icon as cp_icon, cp.color as cp_color,
                src.name as source_label, src.icon as source_icon
            FROM lead_leads l
            LEFT JOIN latest_scorecard ls ON ls.rn = 1
            LEFT JOIN score_items_detail sid ON TRUE
            LEFT JOIN model_criteria mc ON ls.model_id = mc.model_id
            LEFT JOIN lead_statuses st ON l.status_id = st.id
            LEFT JOIN lead_contact_preferences cp ON l.contact_preference_id = cp.id
            LEFT JOIN lead_sources src ON l.source_id = src.id
            WHERE l.id = :id AND l.deleted_at IS NULL
            {access_filter}
            GROUP BY l.id, ls.id, mc.criteria, st.name, st.color, st.icon, 
                     cp.name, cp.icon, cp.color, src.name, src.icon
        """)
        
        async with engine.connect() as conn:
            result = await conn.execute(query_str, params)
            row = result.fetchone()
            return dict(row._mapping) if row else None
    
    async def _fallback_to_legacy_detail(
        self,
        lead_id: UUID,
        user_id: UUID,
        is_superuser: bool,
        tenant_ids: Optional[List[UUID]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fallback to legacy detail when v2 is not enabled.
        """
        from app.modules.leads.service import service as legacy_service
        return await legacy_service.get_lead_by_id(lead_id, user_id, is_superuser, tenant_ids)
    
    async def get_scoring_schema_for_vertical(
        self,
        vertical_id: int,
        scoring_model_id: Optional[UUID] = None,
    ) -> Optional[ScoringSchemaV2]:
        """
        Resolve active scoring schema by vertical (v2 source of truth).
        """
        if not vertical_id:
            return None

        if scoring_model_id:
            model_query = text(
                """
                SELECT
                    m.id AS model_id,
                    m.version AS model_version,
                    m.prompt_version,
                    m.normalization_strategy,
                    v.slug AS vertical_slug
                FROM lead_scoring_models m
                LEFT JOIN lead_client_verticals v ON v.id = m.vertical_id
                WHERE m.id = :model_id
                  AND m.vertical_id = :vertical_id
                  AND m.is_active = true
                LIMIT 1
                """
            )
            model_params = {"vertical_id": vertical_id, "model_id": scoring_model_id}
        else:
            model_query = text(
                """
                SELECT
                    m.id AS model_id,
                    m.version AS model_version,
                    m.prompt_version,
                    m.normalization_strategy,
                    v.slug AS vertical_slug
                FROM lead_scoring_models m
                LEFT JOIN lead_client_verticals v ON v.id = m.vertical_id
                WHERE m.vertical_id = :vertical_id
                  AND m.is_active = true
                ORDER BY m.version DESC
                LIMIT 1
                """
            )
            model_params = {"vertical_id": vertical_id}

        async with engine.connect() as conn:
            model_result = await conn.execute(model_query, model_params)
            model_row = model_result.mappings().first()
            if not model_row:
                return None

            model_id = model_row["model_id"]
            criteria_query = text(
                """
                SELECT
                    c.id AS criterion_id,
                    c.criterion_key,
                    c.label,
                    c.icon,
                    c.weight,
                    c.min_score,
                    c.max_score,
                    c.display_order
                FROM lead_scoring_criteria c
                WHERE c.model_id = :model_id
                  AND c.is_active = true
                ORDER BY c.display_order
                """
            )
            criteria_result = await conn.execute(criteria_query, {"model_id": model_id})
            criteria_rows = criteria_result.mappings().all()

            criteria_payload: List[Dict[str, Any]] = []
            bands_query = text(
                """
                SELECT
                    b.band_key,
                    b.label,
                    b.min_score,
                    b.max_score,
                    b.icon,
                    b.color
                FROM lead_scoring_bands b
                WHERE b.criterion_id = :criterion_id
                ORDER BY b.min_score
                """
            )
            for criterion in criteria_rows:
                band_result = await conn.execute(
                    bands_query, {"criterion_id": criterion["criterion_id"]}
                )
                bands = [dict(band) for band in band_result.mappings().all()]
                criteria_payload.append(
                    {
                        "criterion_key": criterion["criterion_key"],
                        "label": criterion["label"],
                        "icon": criterion.get("icon"),
                        "weight": criterion["weight"],
                        "min_score": criterion["min_score"],
                        "max_score": criterion["max_score"],
                        "display_order": criterion["display_order"],
                        "bands": bands,
                    }
                )

        return ScoringSchemaV2(
            vertical_slug=(model_row.get("vertical_slug") or "generic"),
            model_id=model_row["model_id"],
            model_version=model_row["model_version"],
            prompt_version=model_row["prompt_version"],
            normalization_strategy=model_row["normalization_strategy"],
            criteria=criteria_payload,
        )
    
    def transform_to_scoring_values(self, lead_data: Dict[str, Any]) -> ScoringValuesV2:
        """
        Transform raw lead data with scorecard into ScoringValuesV2 format.
        """
        if not lead_data.get('scorecard_id'):
            # No scorecard exists, return empty values
            return ScoringValuesV2(
                score_total=0.0,
                score_items=[]
            )
        
        score_items = []
        for item in (lead_data.get('score_items_detail') or lead_data.get('score_items') or []):
            if isinstance(item, dict):
                score_items.append(ScoreItemValueV2(
                    criterion_key=item.get('criterion_key', ''),
                    score=float(item.get('score', 0.0)),
                    band_key=item.get('band_key'),
                    band_label=item.get('band_label'),
                    band_color=item.get('band_color'),
                    band_icon=item.get('band_icon'),
                    explanation=item.get('explanation'),
                    normalized_score=self._normalize_score(
                        float(item.get('score', 0.0)),
                        item.get('criterion_key'),
                        lead_data.get('model_criteria', [])
                    )
                ))
        
        return ScoringValuesV2(
            score_total=float(lead_data.get('score_total', 0.0)),
            priority_label=lead_data.get('priority_label'),
            reasoning=lead_data.get('reasoning'),
            score_items=score_items,
            scorecard_id=lead_data.get('scorecard_id'),
            created_at=lead_data.get('scored_at')
        )
    
    def _normalize_score(self, score: float, criterion_key: str, model_criteria: List[Dict]) -> Optional[float]:
        """
        Normalize score to 0-100 range based on criterion min/max.
        """
        if not model_criteria:
            return None
        
        for criterion in model_criteria:
            if criterion.get('criterion_key') == criterion_key:
                min_score = float(criterion.get('min_score', 0.0))
                max_score = float(criterion.get('max_score', 100.0))
                
                if max_score > min_score:
                    return ((score - min_score) / (max_score - min_score)) * 100.0
        
        return None


# Singleton instance
service = LeadsV2Service()
