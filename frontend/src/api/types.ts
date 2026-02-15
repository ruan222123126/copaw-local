export interface ApiErrorShape {
  detail?: string;
  message?: string;
  code?: string | number;
}

export type JsonObject = Record<string, unknown>;

export interface ModelInfo {
  id: string;
  name: string;
}

export interface ProviderInfo {
  id: string;
  name: string;
  api_key_prefix: string;
  models: ModelInfo[];
  allow_custom_base_url: boolean;
  has_api_key: boolean;
  current_api_key: string;
  current_base_url: string;
}

export interface ModelSlotConfig {
  provider_id: string;
  model: string;
}

export interface ActiveModelsInfo {
  active_llm: ModelSlotConfig;
}

export interface EnvVar {
  key: string;
  value: string;
}

export type ChannelType = string;

export type ChannelConfigMap = Record<string, JsonObject>;

export interface SkillSpec {
  name: string;
  content: string;
  source: string;
  path: string;
  references: Record<string, unknown>;
  scripts: Record<string, unknown>;
  enabled: boolean;
}

export interface MdFileInfo {
  filename: string;
  path: string;
  size: number;
  created_time: string;
  modified_time: string;
}

export interface ChatSpec {
  id: string;
  name: string;
  session_id: string;
  user_id: string;
  channel: string;
  created_at: string;
  updated_at: string;
  meta: Record<string, unknown>;
}

export interface RuntimeContent {
  type: string;
  text?: string;
  image_url?: string;
  file_name?: string;
  file_url?: string;
  file_size?: number;
  data?: unknown;
  status?: string;
  [key: string]: unknown;
}

export interface RuntimeMessage {
  id?: string;
  role?: string;
  type?: string;
  metadata?: Record<string, unknown>;
  content?: RuntimeContent[];
}

export interface ChatHistory {
  messages: RuntimeMessage[];
}

export interface PushMessageResponse {
  messages: Array<Record<string, unknown>>;
}

export interface AgentInputMessage {
  role: "user" | "assistant";
  type: "message";
  content: RuntimeContent[];
}

export interface AgentProcessRequest {
  input: AgentInputMessage[];
  session_id: string;
  user_id: string;
  channel: string;
  stream: boolean;
  biz_params?: Record<string, unknown>;
}

export interface CronScheduleSpec {
  type: "cron";
  cron: string;
  timezone: string;
}

export interface CronDispatchTarget {
  user_id: string;
  session_id: string;
}

export interface CronDispatchSpec {
  type: "channel";
  channel: string;
  target: CronDispatchTarget;
  mode: "stream" | "final";
  meta: Record<string, unknown>;
}

export interface CronRuntimeSpec {
  max_concurrency: number;
  timeout_seconds: number;
  misfire_grace_seconds: number;
}

export interface CronJobSpec {
  id: string;
  name: string;
  enabled: boolean;
  schedule: CronScheduleSpec;
  task_type: "text" | "agent";
  text?: string;
  request?: JsonObject;
  dispatch: CronDispatchSpec;
  runtime: CronRuntimeSpec;
  meta: Record<string, unknown>;
}

export interface CronJobState {
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_status?: "success" | "error" | "running" | "skipped" | null;
  last_error?: string | null;
}

export interface CronJobView {
  spec: CronJobSpec;
  state: CronJobState;
}
