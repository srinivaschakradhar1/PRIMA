// Shared domain types matching the FastAPI backend contracts

export type Criticality = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type EquipmentStatus = 'UP' | 'FAILED' | 'SCHEDULED_DOWN' | 'MAINTENANCE';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type DocumentType =
  | 'MANUAL'
  | 'SOP'
  | 'FAILURE_REPORT'
  | 'MAINTENANCE_LOG'
  | 'SPARE_PART';

export interface Plant {
  id: string;
  name: string;
  location: string;
  description?: string;
}

export interface EquipmentListItem {
  id: string;
  equipment_code: string;
  equipment_name: string;
  status: string;
  health_score: number;
  risk_of_failure: RiskLevel | string;
  equipment_type?: string;
  criticality?: Criticality;
  location_in_plant?: string;
}

export interface EquipmentDetail {
  plant_id: string;
  equipment_code: string;
  equipment_name: string;
  equipment_type: string;
  manufacturer: string;
  model_number: string;
  criticality: Criticality;
  expected_life_days: number;
  expected_end_of_life_date: string;
  location_in_plant: string;
  health: string;
  health_score: number;
  risk_of_failure: RiskLevel | string;
}

export interface EquipmentFilter {
  plantId?: string;
  equipmentType?: string;
  status?: string;
  criticality?: string;
}

export interface EquipmentStatusItem {
  equipment_id: string;
  equipment_name: string;
  status: EquipmentStatus | string;
  health_score: number;
  risk_of_failure: RiskLevel | string;
}

export interface EquipmentStatusSummary {
  UP: number;
  FAILED: number;
  SCHEDULED_DOWN: number;
  MAINTENANCE: number;
}

export interface EquipmentHealth {
  equipment_id: string;
  health_score: number;
  risk: RiskLevel | string;
  rul_days: number;
}

export interface PreventiveAction {
  priority: number;
  action: string;
}

export interface PreventiveActionsResponse {
  equipment: string;
  actions: PreventiveAction[];
}

export interface SensorReadingInput {
  equipment_id: string;
  sensor_code: string;
  value: number;
  timestamp: string;
}

export interface SensorReadingBatchResponse {
  accepted: number;
  rejected: number;
}

export interface KnowledgeDocumentSummary {
  document_id: string;
  equipment_id?: string | null;
  equipment_type?: string | null;
  document_type?: DocumentType | string | null;
  document_name?: string | null;
  chunk_count: number;
  ingested_at?: string | null;
}

export interface KnowledgeDocumentListResponse {
  total: number;
  limit: number;
  offset: number;
  documents: KnowledgeDocumentSummary[];
}

export interface KnowledgeDocumentFilter {
  equipmentType?: string;
  equipmentId?: string;
  documentType?: DocumentType;
}

export interface KnowledgeChunk {
  chunk_id: string;
  parent_chunk_id?: string | null;
  is_parent: boolean;
  index_name?: string | null;
  document_type?: string | null;
  concept?: string | null;
  semantic_type?: string | null;
  page?: number | null;
  start_offset?: number | null;
  end_offset?: number | null;
  token_count?: number | null;
  text: string;
}

export interface KnowledgeChunksResponse {
  document_id: string;
  document_name?: string | null;
  total_chunks: number;
  indexed_chunks: number;
  counts_by_index: Record<string, number>;
  chunks: KnowledgeChunk[];
}

export interface KnowledgeUploadResponse {
  document_id: string;
}

export interface KnowledgeIngestionJobResponse {
  job_id: string;
  status: string;
  accepted_files: number;
}

export interface KnowledgeDeleteResponse {
  status: string;
}

export interface ChatCitation {
  document: string;
  page: number;
}

export interface ConversationTurn {
  role: string;
  content: string;
}

export interface ChatRequest {
  session_id: string;
  equipment_code: string;
  conversation_history: ConversationTurn[];
  message: string;
}

export interface ChatResponse {
  response: string;
  citations?: ChatCitation[];
  agent_trace_id?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: ChatCitation[];
  timestamp: string;
  /** Set on a user message whose request failed, so the UI can offer a retry. */
  error?: boolean;
}

export interface DiagnoseRequest {
  equipment_id: string;
  symptoms: string[];
}

export interface RootCause {
  cause: string;
  confidence: number;
}

export interface DiagnoseResponse {
  diagnosis: string;
  confidence: number;
  root_causes: RootCause[];
  recommended_actions: string[];
}

export interface Alert {
  id: string;
  equipment_id: string;
  equipment_name: string;
  alert_type:
    | 'HIGH TEMPERATURE'
    | 'HIGH VIBRATION'
    | 'LOW PRESSURE'
    | 'PREDICTED FAILURE'
    | 'RUL BELOW THRESHOLD'
    | string;
  severity: RiskLevel | string;
  message: string;
  created_at: string;
}

export interface SensorTrendPoint {
  timestamp: string;
  value: number;
}

export interface ApiErrorResponse {
  message: string;
}
