# Alias de compatibilidad: la configuracion de produccion vive en app.config (Fase 2, O5).
from app.config import ProductionConfig  # noqa: F401

__all__ = ["ProductionConfig"]
