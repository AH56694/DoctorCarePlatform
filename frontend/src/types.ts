export type View = "overview" | "accounts" | "consultation" | "jobs" | "profiles" | "chat" | "verification" | "knowledge";

export type Metric = {
  label: string;
  value: string;
  detail: string;
  tone: "green" | "amber" | "blue" | "rose";
};

export type ChatResponse = {
  answer: string;
  intent: {
    category: string;
    subcategory: string;
    confidence: number;
  };
  cache_hit_level: string;
  citations: CitationSource[];
  task_type?: string;
  run_id?: string | null;
  trace_id?: string | null;
  session_id?: string | null;
  steps?: Array<Record<string, unknown>>;
  tool_calls?: Array<Record<string, unknown>>;
  intermediate_conclusions?: Array<Record<string, unknown>>;
};

export type CitationSource = {
  title?: string;
  doc?: string;
  source?: string;
  source_url?: string;
  doc_id?: string | number;
  snippet?: string;
  content?: string;
  page?: string | number;
  chunk_index?: string | number;
  hit_count?: number;
};

export type AiSessionHistory = {
  id: string;
  user_id?: string | null;
  title: string;
  risk_flag: string;
  summary: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AiConversationMessage = {
  id: string;
  session_id?: string | null;
  sender: "user" | "ai" | string;
  content: string;
  intent_category?: string;
  intent_subcategory?: string;
  intent_confidence?: number;
  cache_hit_level?: string;
  metadata_json?: Record<string, unknown>;
  created_at?: string | null;
};

export type StreamProcessEvent = {
  id: string;
  type: "status" | "tool" | "sources" | "error";
  label: string;
  detail: string;
  status?: string;
};

export type AiFlowItem = {
  id: string;
  type: "status" | "tool" | "sources" | "error";
  label: string;
  detail: string;
  status: string;
};

export type JobPosting = {
  id: string;
  employer_id: string;
  patient_id?: string | null;
  title: string;
  city: string;
  care_type: string;
  care_level: string;
  location: string;
  budget_cents: number;
  salary?: { unit?: string; amount_cents?: number; amount_yuan?: number };
  schedule?: Record<string, unknown>;
  status: string;
  special_requirements: string;
  description: string;
};

export type JobApplication = {
  id: string;
  job_id: string;
  caregiver_id: string;
  status: string;
  cover_letter: string;
};

export type AvailableCaregiver = {
  user_id: string;
  real_name: string;
  bio: string;
  service_city: string;
  experience_years: number;
  rating_avg: number;
  is_available: boolean;
};

export type Invitation = {
  id: string;
  patient_id: string;
  caregiver_id: string;
  job_id?: string | null;
  status: string;
  message: string;
};

export type MatchResult = {
  status: string;
  conversation?: {
    id: string;
    title: string;
    source_type: string;
  } | null;
};

export type PatientHomepage = {
  user_id: string;
  display_name: string;
  real_name: string;
  id_verified: boolean;
  verification_status: string;
  basic_info: Record<string, unknown>;
  rating_avg: number;
  review_count: number;
  recent_reviews: Array<{
    id: string;
    reviewer_id: string;
    score: number;
    comment: string;
  }>;
  public_cases: Array<{
    id: string;
    summary: string;
    public_summary: string;
    visibility: string;
  }>;
  job_history: Array<{
    id: string;
    title: string;
    city: string;
    care_type: string;
    location: string;
    budget_cents: number;
    status: string;
  }>;
};

export type CaregiverResume = {
  user_id: string;
  display_name: string;
  real_name: string;
  id_verified: boolean;
  verification_status: string;
  bio: string;
  is_available: boolean;
  experience_years: number;
  service_city: string;
  rating_avg: number;
  review_count: number;
  certifications: Array<{
    id: string;
    certificate_type: string;
    description: string;
    review_status: string;
  }>;
  recent_reviews: Array<{
    id: string;
    reviewer_id: string;
    score: number;
    comment: string;
  }>;
};

export type ServiceReview = {
  id: string;
  conversation_id: string;
  reviewer_id: string;
  reviewee_id: string;
  score: number;
  tags: Array<string>;
  comment: string;
};

export type AdminSummary = {
  users: number;
  active_jobs: number;
  pending_certifications: number;
  ai_sessions: number;
  risk_alerts: number;
  sms_notifications: number;
  reviews: number;
};

export type AdminUser = {
  id: string;
  phone: string;
  display_name: string;
  status: string;
  active_role: string;
};

export type AdminCertification = {
  id: string;
  caregiver_user_id: string;
  caregiver_name: string;
  certificate_type: string;
  file_url: string;
  description: string;
  review_status: string;
  review_note: string;
};

export type AdminAiModelConfig = {
  id: string;
  provider: string;
  model_name: string;
  base_url: string;
  api_key_ref: string;
  temperature: number;
  max_tokens: number;
  is_active: boolean;
};

export type AdminLog = {
  id: string;
  action: string;
  target_type: string;
  target_id: string;
  target: string;
  created_at?: string | null;
};

export type AdminKnowledgeItem = {
  id: string;
  collection: string;
  category: string;
  subcategory: string;
  title: string;
  content: string;
  file_name: string;
  file_type: string;
  rag_doc_id?: number | null;
  rag_status: string;
  rag_chunk_count: number;
  created_at?: string | null;
};

export type RoleName = "patient" | "caregiver" | "admin";

export type AccountRead = {
  id: string;
  phone: string;
  display_name: string;
  status: string;
  active_role: RoleName;
  roles: Array<{
    id: string;
    role: RoleName;
    is_active: boolean;
    verification_status: string;
  }>;
  patient_profile?: {
    real_name: string;
    id_verified: boolean;
    verification_status: string;
    basic_info: Record<string, unknown>;
  } | null;
  caregiver_profile?: {
    real_name: string;
    id_verified: boolean;
    verification_status: string;
    bio: string;
    is_available: boolean;
    experience_years: number;
    service_city: string;
    rating_avg: number;
  } | null;
  certifications: Array<{
    id: string;
    certificate_type: string;
    file_url: string;
    description: string;
    review_status: string;
    review_note: string;
  }>;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  account: AccountRead;
};

export type AiAttachment = {
  file_name: string;
  file_type: string;
  content: string;
};

export type CareConversation = {
  id: string;
  owner_id: string;
  participant_a?: string | null;
  participant_b?: string | null;
  kind: string;
  source_type: string;
  source_id?: string | null;
  title: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CareMessage = {
  id: string;
  conversation_id: string;
  sender_id?: string | null;
  sender_type: string;
  body: string;
  content: string;
  attachment_url: string;
  attachment_type: string;
  created_at?: string | null;
};
