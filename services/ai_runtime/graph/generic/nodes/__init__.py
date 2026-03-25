"""Generic graph nodes package."""

from services.ai_runtime.graph.generic.nodes.assign_agent_node import assign_agent
from services.ai_runtime.graph.generic.nodes.collect_appointment_data_node import collect_appointment_data
from services.ai_runtime.graph.generic.nodes.rag_agencia_node import rag_agencia

__all__ = ["assign_agent", "collect_appointment_data", "rag_agencia"]
