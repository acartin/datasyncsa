"""
Plan de Rollout y Rollback para Chat Multi-Canal

Este documento define el plan de despliegue gradual y procedimientos de rollback.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class RolloutStage(str, Enum):
    """Etapas del rollout."""
    DISABLED = "disabled"
    CANARY = "canary"
    DELTA = "delta"
    GENERAL = "general"
    FULL = "full"


@dataclass
class RolloutConfig:
    """Configuración de rollout para un feature."""
    feature_name: str
    stage: RolloutStage
    percentage: int
    allowed_clients: List[str]
    blocked_clients: List[str]
    description: str


ROLLOUT_CONFIG: Dict[str, RolloutConfig] = {
    "CHANNEL_GATEWAY": RolloutConfig(
        feature_name="CHANNEL_GATEWAY",
        stage=RolloutStage.FULL,
        percentage=100,
        allowed_clients=[],
        blocked_clients=[],
        description="Gateway multi-canal habilitado para todos",
    ),
    "VERTICAL_ROUTING": RolloutConfig(
        feature_name="VERTICAL_ROUTING",
        stage=RolloutStage.FULL,
        percentage=100,
        allowed_clients=[],
        blocked_clients=[],
        description="Routing por vertical habilitado",
    ),
    "META_ADAPTER": RolloutConfig(
        feature_name="META_ADAPTER",
        stage=RolloutStage.CANARY,
        percentage=10,
        allowed_clients=["client-001", "client-002"],
        blocked_clients=[],
        description="Adapter Meta en rollout canary (10%)",
    ),
    "SESSION_MULTICHANNEL": RolloutConfig(
        feature_name="SESSION_MULTICHANNEL",
        stage=RolloutStage.DISABLED,
        percentage=0,
        allowed_clients=["client-001"],
        blocked_clients=[],
        description="Sesión multi-canal deshabilitada por defecto",
    ),
}


CANARY_CLIENTS = [
    "64f357a0-98eb-44f1-9f41-6e615ed26180",
]

CRITICAL_CLIENTS = [
    "admin-console",
]


def should_enable_feature(
    feature_name: str,
    client_id: str,
    default_enabled: bool = False,
) -> bool:
    """
    Determina si un feature debe estar habilitado para un cliente.
    
    Args:
        feature_name: Nombre del feature flag
        client_id: ID del cliente
        default_enabled: Si es True, el feature está habilitado por defecto
    
    Returns:
        True si el feature debe estar habilitado
    """
    config = ROLLOUT_CONFIG.get(feature_name)
    if not config:
        return default_enabled
    
    if config.stage == RolloutStage.DISABLED:
        return False
    
    if config.stage == RolloutStage.FULL:
        return True
    
    if client_id in config.blocked_clients:
        return False
    
    if client_id in config.allowed_clients:
        return True
    
    if config.stage == RolloutStage.CANARY:
        return client_id in CANARY_CLIENTS
    
    if config.stage == RolloutStage.DELTA:
        client_hash = hash(client_id) % 100
        return client_hash < config.percentage
    
    return default_enabled


def get_rollout_status() -> Dict[str, Any]:
    """Retorna el estado actual del rollout."""
    return {
        feature: {
            "stage": config.stage.value,
            "percentage": config.percentage,
            "description": config.description,
        }
        for feature, config in ROLLOUT_CONFIG.items()
    }


ROLLBACK_PROCEDURE = """
=========================================
PROCEDIMIENTO DE ROLLBACK
=========================================

ESCENARIO: Problemas en producción con nueva funcionalidad

PASO 1: Identificar el problema
---------------------------------
- Verificar logs en: docker compose logs realtor-api
- Buscar errores con: grep ERROR logs
- Verificar latency: latency_ms > 5000

PASO 2: Rollback de emergencia
--------------------------------
# Deshabilitar feature específico
export CHANNEL_GATEWAY_ENABLED=false
export VERTICAL_ROUTING_ENABLED=false  
export META_ADAPTER_ENABLED=false
export SESSION_MULTICHANNEL_ENABLED=false

# Reiniciar servicio
docker compose restart realtor-api

PASO 3: Verificar rollback
--------------------------------
- Ejecutar /health endpoint
- Probar con cliente canary conocido
- Verificar que no hay errores 5xx

PASO 4: Comunicación
------------------------
- Notificar al equipo de #incidents
- Documentar en PENDING_HANDOFF.md
- Planificar post-mortem

=========================================
CHECKLIST DE RELEASE
=========================================

ANTES DEL DEPLOY:
[ ] Tests unitarios pasando (110+ tests)
[ ] Tests de integración pasando
[ ] Smoke tests pasando
[ ] Feature flags configurados correctamente
[ ] Plan de rollback revisado
[ ] Equipo de on-call notificado

DESPUÉS DEL DEPLOY:
[ ] Verificar /health endpoint
[ ] Monitorear latencia (latency_ms < 2000)
[ ] Verificar errores (error count < 1%)
[ ] Probar con cliente canary
[ ] Actualizar estado en PENDING_HANDOFF.md

ROLLBACK CRITERIA:
[ ] Latencia promedio > 5000ms por 5 minutos
[ ] Error rate > 5%
[ ] Clientes críticos reportando problemas
[ ] Memory leak detectado
"""


def print_rollout_plan():
    """Imprime el plan de rollout."""
    print("=========================================")
    print("PLAN DE ROLLOUT - CHAT MULTI-CANAL")
    print("=========================================\n")
    
    print("FASE 1: Baseline (Completado)")
    print("  - Contratos canónicos implementados")
    print("  - Session manager con TTL configurable")
    print("  - Vertical router con fallback")
    print()
    
    print("FASE 2: Web HTML (Activo)")
    print("  - Channel: web_html")
    print("  - Verticales: realtor, generic")
    print("  - Status: FULL (100%)")
    print()
    
    print("FASE 3: Meta Channels (Canary)")
    print("  - Channel: meta_whatsapp, meta_ig")
    print("  - Verticales: realtor, generic")
    print("  - Status: CANARY (10%)")
    print("  - Clientes canary: client-001, client-002")
    print()
    
    print("FASE 4: API Externa")
    print("  - Estado: fuera de scope (v1 retirada)")
    print()
    
    print("=========================================")
    print("VARIABLES DE FEATURE FLAGS")
    print("=========================================")
    
    for feature, config in ROLLOUT_CONFIG.items():
        print(f"\n{feature}:")
        print(f"  Stage: {config.stage.value}")
        print(f"  Percentage: {config.percentage}%")
        print(f"  Description: {config.description}")
