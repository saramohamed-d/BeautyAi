export interface ComponentStatus {
  name: string;
  status: "ok" | "error";
  detail?: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  app_env: string;
  components: ComponentStatus[];
}
