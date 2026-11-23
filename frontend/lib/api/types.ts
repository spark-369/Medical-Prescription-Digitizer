/** Mirrors the backend Pydantic v2 response schemas. */

export type Role = "admin" | "doctor" | "staff";

export type PrescriptionStatus =
  | "uploaded"
  | "queued"
  | "processing"
  | "completed"
  | "failed";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface PrescriptionItem {
  id: string;
  medication: string;
  dosage: string | null;
  frequency: string | null;
  duration: string | null;
  instructions: string | null;
}

export interface PrescriptionBrief {
  id: string;
  status: PrescriptionStatus;
  original_filename: string;
  patient_name: string | null;
  doctor_name: string | null;
  prescribed_date: string | null;
  created_at: string;
}

export interface Prescription extends PrescriptionBrief {
  mime_type: string;
  file_size: number;
  error: string | null;
  raw_output: string | null;
  confidence: number | null;
  model_name: string | null;
  patient_age: number | null;
  notes: string | null;
  processing_started_at: string | null;
  completed_at: string | null;
  updated_at: string;
  items: PrescriptionItem[];
  ai_insights: Insights | null;
  ai_insights_status: "pending" | "ready" | "failed" | null;
  ai_insights_model: string | null;
  ai_insights_generated_at: string | null;
}

// --- AI insights ------------------------------------------------------------

export type InteractionSeverity = "low" | "moderate" | "high" | "unknown";
export type RiskLevel = "none" | "low" | "moderate" | "high" | "unknown";

export interface InteractionFinding {
  medications: string[];
  severity: InteractionSeverity;
  description: string;
  recommendation: string;
}

export interface InteractionReport {
  risk_level: RiskLevel;
  findings: InteractionFinding[];
  general_advice: string | null;
}

export interface ScheduleMedication {
  medication: string;
  times: string[];
  days: number;
  instructions: string | null;
}

export interface MedicationSchedule {
  daily_plan: ScheduleMedication[];
  notes: string | null;
}

export interface Insights {
  summary: string;
  key_points: string[];
  interactions: InteractionReport;
  schedule: MedicationSchedule;
}

// --- AI assistant & reports --------------------------------------------------

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ReportHighlight {
  title: string;
  detail: string;
}

export interface ReportContent {
  headline: string;
  overview: string;
  highlights: ReportHighlight[];
  recommendations: string[];
}

export interface AiReport {
  id: string;
  status: "pending" | "ready" | "failed";
  content: ReportContent | null;
  model: string | null;
  created_at: string;
}

export interface PrescriptionList {
  items: PrescriptionBrief[];
  total: number;
  page: number;
  page_size: number;
}

export interface Stats {
  total: number;
  by_status: Record<string, number>;
  recent: PrescriptionBrief[];
}
