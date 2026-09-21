from pydantic import BaseModel


class ComponentStatus(BaseModel):
    name: str
    status: str  # "ok" | "error"
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded"
    app_env: str
    components: list[ComponentStatus]
