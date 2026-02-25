from typing import List, Optional
from uuid import UUID
from sqlalchemy import text
from app.dal.database import engine

class LeadService:
    async def get_my_leads(
        self,
        user_id: UUID,
        is_superuser: bool = False,
        tenant_ids: Optional[List[UUID]] = None,
    ) -> List[dict]:
        """
        Fetches leads for grid display based on user scope.
        """
        access_filter = ""
        params = {"uid": user_id}
        if not is_superuser:
            if tenant_ids:
                access_filter = "AND (l.assigned_user_id = :uid OR l.client_id = ANY(:tenant_ids))"
                params["tenant_ids"] = tenant_ids
            else:
                access_filter = "AND l.assigned_user_id = :uid"

        query_str = text("""
            SELECT 
                l.id, l.full_name, l.email, l.phone, l.score_total, l.created_at,
                st.name as status_label, st.color as status_color, st.icon as status_icon,
                l.score_engagement, d_eng.icon as eng_icon, d_eng.color as eng_color, d_eng.label as eng_label,
                l.score_finance, d_fin.icon as fin_icon, d_fin.color as fin_color, d_fin.label as fin_label,
                l.score_timeline, d_tim.icon as tim_icon, d_tim.color as tim_color, d_tim.label as tim_label,
                l.score_match, d_mat.icon as mat_icon, d_mat.color as mat_color, d_mat.label as mat_label,
                l.score_info, d_inf.icon as inf_icon, d_inf.color as inf_color, d_inf.label as inf_label,
                d_prio.color as prio_color, d_prio.label as prio_label,
                cp.name as cp_label, cp.icon as cp_icon, cp.color as cp_color,
                d_wf.icon as wf_icon, d_wf.color as wf_color, d_wf.label as wf_label
            FROM lead_leads l
            LEFT JOIN lead_statuses st ON l.status_id = st.id
            LEFT JOIN lead_contact_preferences cp ON l.contact_preference_id = cp.id
            LEFT JOIN lead_scoring_definitions d_eng ON l.eng_def_id = d_eng.id
            LEFT JOIN lead_scoring_definitions d_fin ON l.fin_def_id = d_fin.id
            LEFT JOIN lead_scoring_definitions d_tim ON l.timeline_def_id = d_tim.id
            LEFT JOIN lead_scoring_definitions d_mat ON l.match_def_id = d_mat.id
            LEFT JOIN lead_scoring_definitions d_inf ON l.info_def_id = d_inf.id
            LEFT JOIN lead_scoring_definitions d_prio ON l.priority_def_id = d_prio.id
            LEFT JOIN lead_scoring_definitions d_wf ON d_wf.criterion = 'workflow' AND d_wf.is_active = true
            WHERE l.deleted_at IS NULL
            """ + access_filter + """
            ORDER BY l.score_total DESC, l.created_at DESC
        """)
        
        async with engine.connect() as conn:
            result = await conn.execute(query_str, params)
            rows = result.all()
            return [dict(row._mapping) for row in rows]

    async def get_lead_by_id(
        self,
        lead_id: UUID,
        user_id: UUID,
        is_superuser: bool,
        tenant_ids: Optional[List[UUID]] = None,
    ) -> Optional[dict]:
        """
        Fetches deep data for a single lead, including all relations and scoring details.
        """
        access_filter = ""
        params = {"id": lead_id, "user_id": user_id}
        if not is_superuser:
            if tenant_ids:
                access_filter = " AND (l.assigned_user_id = :user_id OR l.client_id = ANY(:tenant_ids))"
                params["tenant_ids"] = tenant_ids
            else:
                access_filter = " AND l.assigned_user_id = :user_id"

        query_str = text(f"""
            SELECT 
                l.*,
                st.name as status_label, st.color as status_color, st.icon as status_icon,
                cp.name as cp_label, cp.icon as cp_icon, cp.color as cp_color,
                d_eng.icon as eng_icon, d_eng.color as eng_color, d_eng.label as eng_label,
                d_fin.icon as fin_icon, d_fin.color as fin_color, d_fin.label as fin_label,
                d_tim.icon as tim_icon, d_tim.color as tim_color, d_tim.label as tim_label,
                d_mat.icon as mat_icon, d_mat.color as mat_color, d_mat.label as mat_label,
                d_inf.icon as inf_icon, d_inf.color as inf_color, d_inf.label as inf_label,
                d_prio.color as prio_color, d_prio.label as prio_label,
                d_wf.icon as wf_icon, d_wf.color as wf_color, d_wf.label as wf_label,
                src.name as source_label, src.icon as source_icon
            FROM lead_leads l
            LEFT JOIN lead_statuses st ON l.status_id = st.id
            LEFT JOIN lead_contact_preferences cp ON l.contact_preference_id = cp.id
            LEFT JOIN lead_scoring_definitions d_eng ON l.eng_def_id = d_eng.id
            LEFT JOIN lead_scoring_definitions d_fin ON l.fin_def_id = d_fin.id
            LEFT JOIN lead_scoring_definitions d_tim ON l.timeline_def_id = d_tim.id
            LEFT JOIN lead_scoring_definitions d_mat ON l.match_def_id = d_mat.id
            LEFT JOIN lead_scoring_definitions d_inf ON l.info_def_id = d_inf.id
            LEFT JOIN lead_scoring_definitions d_prio ON l.priority_def_id = d_prio.id
            LEFT JOIN lead_scoring_definitions d_wf ON d_wf.criterion = 'workflow' AND d_wf.is_active = true
            LEFT JOIN lead_sources src ON l.source_id = src.id
            WHERE l.id = :id AND l.deleted_at IS NULL
            {access_filter}
        """)
        
        async with engine.connect() as conn:
            result = await conn.execute(query_str, params)
            row = result.fetchone()
            return dict(row._mapping) if row else None

    async def get_my_appointments(self, user_id: UUID) -> List[dict]:
        """
        Fetches coming appointments for leads assigned to the user.
        """
        query = text("""
            SELECT a.id, a.scheduled_at, a.meeting_type, a.status, l.full_name as lead_name
            FROM lead_appointments a
            JOIN lead_leads l ON a.lead_id = l.id
            WHERE l.assigned_user_id = :user_id 
              AND a.deleted_at IS NULL
              AND a.scheduled_at >= CURRENT_DATE
            ORDER BY a.scheduled_at ASC
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, {"user_id": user_id})
            return [dict(row._mapping) for row in result.all()]

service = LeadService()
