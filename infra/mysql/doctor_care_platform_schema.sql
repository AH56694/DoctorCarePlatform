CREATE DATABASE IF NOT EXISTS doctor_care_platform
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE doctor_care_platform;

CREATE TABLE IF NOT EXISTS users (
  id CHAR(36) PRIMARY KEY,
  phone VARCHAR(32) NOT NULL,
  password_hash VARCHAR(255) NOT NULL DEFAULT '',
  display_name VARCHAR(80) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  active_role VARCHAR(32) NOT NULL DEFAULT 'patient',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_users_phone (phone),
  KEY ix_users_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS user_roles (
  id CHAR(36) PRIMARY KEY,
  user_id CHAR(36) NOT NULL,
  role VARCHAR(32) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT FALSE,
  verification_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_user_roles_user_role (user_id, role),
  KEY ix_user_roles_role (role),
  CONSTRAINT fk_user_roles_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS patient_profiles (
  id CHAR(36) PRIMARY KEY,
  user_id CHAR(36) NOT NULL,
  real_name VARCHAR(80) NOT NULL DEFAULT '',
  id_number VARCHAR(64) NOT NULL DEFAULT '',
  id_verified BOOLEAN NOT NULL DEFAULT FALSE,
  verification_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  basic_info JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_patient_profiles_user_id (user_id),
  CONSTRAINT fk_patient_profiles_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS caregiver_profiles (
  id CHAR(36) PRIMARY KEY,
  user_id CHAR(36) NOT NULL,
  real_name VARCHAR(80) NOT NULL DEFAULT '',
  id_number VARCHAR(64) NOT NULL DEFAULT '',
  id_verified BOOLEAN NOT NULL DEFAULT FALSE,
  verification_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  bio TEXT NULL,
  is_available BOOLEAN NOT NULL DEFAULT TRUE,
  experience_years INT NOT NULL DEFAULT 0,
  service_city VARCHAR(80) NOT NULL DEFAULT '',
  rating_avg DECIMAL(3,2) NOT NULL DEFAULT 0.00,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_caregiver_profiles_user_id (user_id),
  KEY ix_caregiver_profiles_available_city (is_available, service_city),
  CONSTRAINT fk_caregiver_profiles_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS certifications (
  id CHAR(36) PRIMARY KEY,
  caregiver_profile_id CHAR(36) NOT NULL,
  certificate_type VARCHAR(80) NOT NULL,
  file_url VARCHAR(500) NOT NULL DEFAULT '',
  description TEXT NULL,
  review_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  review_note TEXT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_certifications_review_status (review_status),
  CONSTRAINT fk_certifications_caregiver_profile_id
    FOREIGN KEY (caregiver_profile_id) REFERENCES caregiver_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS ai_sessions (
  id CHAR(36) PRIMARY KEY,
  user_id CHAR(36) NULL,
  role_context VARCHAR(32) NOT NULL DEFAULT 'patient',
  title VARCHAR(160) NOT NULL DEFAULT '',
  risk_flag VARCHAR(32) NOT NULL DEFAULT 'none',
  summary TEXT NULL,
  metadata_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_ai_sessions_user_id (user_id),
  KEY ix_ai_sessions_risk_flag (risk_flag),
  CONSTRAINT fk_ai_sessions_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS medical_cases (
  id CHAR(36) PRIMARY KEY,
  patient_owner_id CHAR(36) NOT NULL,
  patient_id CHAR(36) NULL,
  summary TEXT NULL,
  public_summary TEXT NULL,
  history_encrypted TEXT NULL,
  symptoms_encrypted TEXT NULL,
  medications_encrypted TEXT NULL,
  encrypted_payload MEDIUMTEXT NULL,
  attachments JSON NULL,
  visibility VARCHAR(32) NOT NULL DEFAULT 'private',
  linked_ai_session_id CHAR(36) NULL,
  encryption_key_version VARCHAR(32) NOT NULL DEFAULT 'v1',
  encryption_metadata JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_medical_cases_patient_owner_id (patient_owner_id),
  KEY ix_medical_cases_patient_id (patient_id),
  KEY ix_medical_cases_visibility (visibility),
  CONSTRAINT fk_medical_cases_patient_owner_id FOREIGN KEY (patient_owner_id) REFERENCES users(id),
  CONSTRAINT fk_medical_cases_patient_id FOREIGN KEY (patient_id) REFERENCES users(id),
  CONSTRAINT fk_medical_cases_linked_ai_session_id
    FOREIGN KEY (linked_ai_session_id) REFERENCES ai_sessions(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS job_postings (
  id CHAR(36) PRIMARY KEY,
  employer_id CHAR(36) NOT NULL,
  patient_id CHAR(36) NULL,
  title VARCHAR(120) NOT NULL,
  city VARCHAR(80) NOT NULL DEFAULT '',
  care_type VARCHAR(80) NOT NULL DEFAULT '',
  care_level VARCHAR(64) NOT NULL DEFAULT '',
  location VARCHAR(160) NOT NULL DEFAULT '',
  schedule JSON NULL,
  salary JSON NULL,
  budget_cents INT NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  special_requirements TEXT NULL,
  description TEXT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_job_postings_employer_id (employer_id),
  KEY ix_job_postings_patient_id (patient_id),
  KEY ix_job_postings_status (status),
  KEY ix_job_postings_city (city),
  CONSTRAINT fk_job_postings_employer_id FOREIGN KEY (employer_id) REFERENCES users(id),
  CONSTRAINT fk_job_postings_patient_id FOREIGN KEY (patient_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS applications (
  id CHAR(36) PRIMARY KEY,
  job_id CHAR(36) NOT NULL,
  caregiver_id CHAR(36) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'submitted',
  cover_letter TEXT NULL,
  idempotency_key VARCHAR(64) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_applications_job_caregiver (job_id, caregiver_id),
  UNIQUE KEY uq_applications_idempotency_key (idempotency_key),
  KEY ix_applications_caregiver_id (caregiver_id),
  KEY ix_applications_status (status),
  CONSTRAINT fk_applications_job_id FOREIGN KEY (job_id) REFERENCES job_postings(id) ON DELETE CASCADE,
  CONSTRAINT fk_applications_caregiver_id FOREIGN KEY (caregiver_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS recruitment_interactions (
  id CHAR(36) PRIMARY KEY,
  patient_id CHAR(36) NOT NULL,
  caregiver_id CHAR(36) NULL,
  job_id CHAR(36) NULL,
  action_type VARCHAR(32) NOT NULL,
  action_weight DOUBLE NOT NULL DEFAULT 0,
  context_json JSON NULL,
  request_id VARCHAR(64) NOT NULL DEFAULT '',
  model_version VARCHAR(120) NOT NULL DEFAULT '',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_recruitment_interactions_patient_created (patient_id, created_at),
  KEY ix_recruitment_interactions_caregiver_created (caregiver_id, created_at),
  KEY ix_recruitment_interactions_job_created (job_id, created_at),
  KEY ix_recruitment_interactions_action_created (action_type, created_at),
  KEY ix_recruitment_interactions_request_id (request_id),
  CONSTRAINT fk_recruitment_interactions_patient_id
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_recruitment_interactions_caregiver_id
    FOREIGN KEY (caregiver_id) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT fk_recruitment_interactions_job_id
    FOREIGN KEY (job_id) REFERENCES job_postings(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS invitations (
  id CHAR(36) PRIMARY KEY,
  patient_id CHAR(36) NOT NULL,
  caregiver_id CHAR(36) NOT NULL,
  job_id CHAR(36) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  message TEXT NULL,
  idempotency_key VARCHAR(64) NULL,
  responded_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_invitations_patient_caregiver_job (patient_id, caregiver_id, job_id),
  UNIQUE KEY uq_invitations_idempotency_key (idempotency_key),
  KEY ix_invitations_caregiver_id (caregiver_id),
  KEY ix_invitations_status (status),
  CONSTRAINT fk_invitations_patient_id FOREIGN KEY (patient_id) REFERENCES users(id),
  CONSTRAINT fk_invitations_caregiver_id FOREIGN KEY (caregiver_id) REFERENCES users(id),
  CONSTRAINT fk_invitations_job_id FOREIGN KEY (job_id) REFERENCES job_postings(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS conversations (
  id CHAR(36) PRIMARY KEY,
  owner_id CHAR(36) NOT NULL,
  participant_a CHAR(36) NULL,
  participant_b CHAR(36) NULL,
  kind VARCHAR(32) NOT NULL DEFAULT 'care_chat',
  source_type VARCHAR(32) NOT NULL DEFAULT '',
  source_id CHAR(36) NULL,
  title VARCHAR(160) NOT NULL DEFAULT '',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_conversations_owner_id (owner_id),
  KEY ix_conversations_participant_a (participant_a),
  KEY ix_conversations_participant_b (participant_b),
  KEY ix_conversations_source (source_type, source_id),
  CONSTRAINT fk_conversations_owner_id FOREIGN KEY (owner_id) REFERENCES users(id),
  CONSTRAINT fk_conversations_participant_a FOREIGN KEY (participant_a) REFERENCES users(id),
  CONSTRAINT fk_conversations_participant_b FOREIGN KEY (participant_b) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS messages (
  id CHAR(36) PRIMARY KEY,
  conversation_id CHAR(36) NOT NULL,
  sender_id CHAR(36) NULL,
  sender_type VARCHAR(32) NOT NULL DEFAULT 'user',
  body TEXT NULL,
  content TEXT NULL,
  attachment_url VARCHAR(500) NOT NULL DEFAULT '',
  attachment_type VARCHAR(64) NOT NULL DEFAULT '',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_messages_conversation_id (conversation_id),
  KEY ix_messages_sender_id (sender_id),
  CONSTRAINT fk_messages_conversation_id FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
  CONSTRAINT fk_messages_sender_id FOREIGN KEY (sender_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS ai_messages (
  id CHAR(36) PRIMARY KEY,
  session_id CHAR(36) NULL,
  conversation_id CHAR(36) NULL,
  sender VARCHAR(16) NOT NULL DEFAULT 'user',
  content TEXT NULL,
  user_message TEXT NULL,
  assistant_message TEXT NULL,
  intent_category VARCHAR(64) NOT NULL DEFAULT '',
  intent_subcategory VARCHAR(64) NOT NULL DEFAULT '',
  intent_confidence DECIMAL(5,4) NOT NULL DEFAULT 0.0000,
  cache_hit_level VARCHAR(16) NOT NULL DEFAULT 'miss',
  metadata_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_ai_messages_session_id (session_id),
  KEY ix_ai_messages_intent_category (intent_category),
  KEY ix_ai_messages_intent_subcategory (intent_subcategory),
  CONSTRAINT fk_ai_messages_session_id FOREIGN KEY (session_id) REFERENCES ai_sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS ai_model_configs (
  id CHAR(36) PRIMARY KEY,
  provider VARCHAR(64) NOT NULL DEFAULT 'deepseek',
  model_name VARCHAR(120) NOT NULL DEFAULT 'deepseek-chat',
  base_url VARCHAR(500) NOT NULL DEFAULT 'https://api.deepseek.com',
  api_key_ref VARCHAR(120) NOT NULL DEFAULT 'LLM_API_KEY',
  temperature DECIMAL(4,3) NOT NULL DEFAULT 0.300,
  max_tokens INT NOT NULL DEFAULT 2048,
  is_active BOOLEAN NOT NULL DEFAULT FALSE,
  parameters JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_ai_model_configs_provider (provider),
  KEY ix_ai_model_configs_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT IGNORE INTO ai_model_configs (
  id, provider, model_name, base_url, api_key_ref, temperature, max_tokens, is_active, parameters
) VALUES (
  '00000000-0000-0000-0000-000000000003',
  'deepseek',
  'deepseek-chat',
  'https://api.deepseek.com',
  'LLM_API_KEY',
  0.300,
  2048,
  TRUE,
  JSON_OBJECT()
);

CREATE TABLE IF NOT EXISTS ai_knowledge_chunks (
  id CHAR(36) PRIMARY KEY,
  category VARCHAR(64) NOT NULL,
  subcategory VARCHAR(64) NOT NULL,
  collection VARCHAR(128) NOT NULL,
  content MEDIUMTEXT NOT NULL,
  embedding JSON NULL,
  source_url TEXT NULL,
  crawled_at DATETIME(6) NULL,
  metadata_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_ai_knowledge_chunks_category (category),
  KEY ix_ai_knowledge_chunks_subcategory (subcategory),
  KEY ix_ai_knowledge_chunks_collection (collection)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS ai_semantic_cache (
  id CHAR(36) PRIMARY KEY,
  category VARCHAR(64) NOT NULL,
  subcategory VARCHAR(64) NOT NULL,
  query_text TEXT NOT NULL,
  query_embedding JSON NULL,
  answer_text MEDIUMTEXT NULL,
  cached_answer MEDIUMTEXT NULL,
  intent_category VARCHAR(64) NOT NULL DEFAULT '',
  reusable_as_final BOOLEAN NOT NULL DEFAULT FALSE,
  cache_policy VARCHAR(32) NOT NULL DEFAULT 'context_only',
  ttl_seconds INT NOT NULL DEFAULT 0,
  expires_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_ai_semantic_cache_category (category),
  KEY ix_ai_semantic_cache_subcategory (subcategory),
  KEY ix_ai_semantic_cache_intent_category (intent_category),
  KEY ix_ai_semantic_cache_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS reviews (
  id CHAR(36) PRIMARY KEY,
  conversation_id CHAR(36) NOT NULL,
  reviewer_id CHAR(36) NOT NULL,
  reviewee_id CHAR(36) NOT NULL,
  score TINYINT NOT NULL,
  tags JSON NULL,
  comment TEXT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_reviews_conversation_reviewer (conversation_id, reviewer_id),
  KEY ix_reviews_reviewee_id (reviewee_id),
  CONSTRAINT ck_reviews_score_range CHECK (score BETWEEN 1 AND 5),
  CONSTRAINT fk_reviews_conversation_id FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
  CONSTRAINT fk_reviews_reviewer_id FOREIGN KEY (reviewer_id) REFERENCES users(id),
  CONSTRAINT fk_reviews_reviewee_id FOREIGN KEY (reviewee_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS sms_notifications (
  id CHAR(36) PRIMARY KEY,
  user_id CHAR(36) NULL,
  scene VARCHAR(64) NOT NULL DEFAULT '',
  phone VARCHAR(32) NOT NULL,
  template_code VARCHAR(80) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'queued',
  provider_message_id VARCHAR(128) NOT NULL DEFAULT '',
  payload JSON NULL,
  sent_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_sms_notifications_user_id (user_id),
  KEY ix_sms_notifications_phone (phone),
  KEY ix_sms_notifications_scene (scene),
  CONSTRAINT fk_sms_notifications_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS admin_logs (
  id CHAR(36) PRIMARY KEY,
  admin_id CHAR(36) NULL,
  action VARCHAR(120) NOT NULL,
  target_type VARCHAR(80) NOT NULL DEFAULT '',
  target_id VARCHAR(120) NOT NULL DEFAULT '',
  target VARCHAR(200) NOT NULL DEFAULT '',
  detail JSON NULL,
  ip_address VARCHAR(64) NOT NULL DEFAULT '',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY ix_admin_logs_admin_id (admin_id),
  KEY ix_admin_logs_action (action),
  KEY ix_admin_logs_target (target_type, target_id),
  CONSTRAINT fk_admin_logs_admin_id FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Python-service legacy/agent tables
-- These tables keep the migrated Python AI service compatible with its
-- existing agents while the main platform keeps richer ai_* tables above.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS knowledge_doc (
  id BIGINT PRIMARY KEY,
  title VARCHAR(255) NOT NULL DEFAULT '',
  source VARCHAR(500) NOT NULL DEFAULT '',
  file_name VARCHAR(255) NOT NULL DEFAULT '',
  file_type VARCHAR(120) NOT NULL DEFAULT '',
  collection VARCHAR(128) NOT NULL DEFAULT 'medical.symptom_inquiry',
  category VARCHAR(64) NOT NULL DEFAULT 'medical',
  subcategory VARCHAR(64) NOT NULL DEFAULT 'symptom_inquiry',
  metadata_json JSON NULL,
  create_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  created_at DATETIME(6) GENERATED ALWAYS AS (create_time) VIRTUAL,
  updated_at DATETIME(6) GENERATED ALWAYS AS (update_time) VIRTUAL,
  KEY ix_knowledge_doc_collection (collection),
  KEY ix_knowledge_doc_category (category),
  KEY ix_knowledge_doc_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS knowledge_chunk (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  doc_id BIGINT NOT NULL,
  chunk_index INT NOT NULL DEFAULT 0,
  chunk_text MEDIUMTEXT NOT NULL,
  content MEDIUMTEXT NULL,
  score DECIMAL(8,6) NOT NULL DEFAULT 0.000000,
  metadata_json JSON NULL,
  create_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  created_at DATETIME(6) GENERATED ALWAYS AS (create_time) VIRTUAL,
  updated_at DATETIME(6) GENERATED ALWAYS AS (update_time) VIRTUAL,
  UNIQUE KEY uq_knowledge_chunk_doc_index (doc_id, chunk_index),
  KEY ix_knowledge_chunk_doc_id (doc_id),
  KEY ix_knowledge_chunk_create_time (create_time),
  CONSTRAINT fk_knowledge_chunk_doc_id FOREIGN KEY (doc_id) REFERENCES knowledge_doc(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS qa_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  userId VARCHAR(64) NOT NULL DEFAULT '',
  conversation_id VARCHAR(64) NOT NULL DEFAULT '',
  question TEXT NOT NULL,
  answer MEDIUMTEXT NULL,
  intent_category VARCHAR(64) NOT NULL DEFAULT '',
  intent_subcategory VARCHAR(64) NOT NULL DEFAULT '',
  cache_hit_level VARCHAR(32) NOT NULL DEFAULT 'miss',
  create_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY ix_qa_log_userId (userId),
  KEY ix_qa_log_create_time (create_time),
  KEY ix_qa_log_intent_category (intent_category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS qa_unanswered (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  question TEXT NOT NULL,
  count INT NOT NULL DEFAULT 1,
  last_seen_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  create_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY ix_qa_unanswered_count (count),
  KEY ix_qa_unanswered_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS user_memory (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  memory_key VARCHAR(120) NOT NULL,
  memory_value JSON NOT NULL,
  source VARCHAR(64) NOT NULL DEFAULT 'agent',
  confidence DECIMAL(5,4) NOT NULL DEFAULT 1.0000,
  create_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_user_memory_user_key (user_id, memory_key),
  KEY ix_user_memory_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS agent_run (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id CHAR(36) NOT NULL,
  trace_id CHAR(36) NULL,
  user_id VARCHAR(64) NOT NULL DEFAULT '',
  task_type VARCHAR(64) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'running',
  start_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  end_time DATETIME(6) NULL,
  duration_ms DECIMAL(12,3) NULL,
  error_message TEXT NULL,
  metadata_json JSON NULL,
  UNIQUE KEY uq_agent_run_run_id (run_id),
  KEY ix_agent_run_status (status),
  KEY ix_agent_run_start_time (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS tool_call (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  tool_call_id CHAR(36) NOT NULL,
  run_id CHAR(36) NOT NULL,
  tool_name VARCHAR(120) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'running',
  duration_ms DECIMAL(12,3) NULL,
  error_message TEXT NULL,
  input_params JSON NULL,
  output JSON NULL,
  timestamp DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_tool_call_id (tool_call_id),
  KEY ix_tool_call_run_id (run_id),
  KEY ix_tool_call_status (status),
  KEY ix_tool_call_tool_name (tool_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS doc_view_logs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  doc_id BIGINT NOT NULL,
  user_id VARCHAR(64) NOT NULL DEFAULT '',
  create_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY ix_doc_view_logs_doc_id (doc_id),
  KEY ix_doc_view_logs_create_time (create_time),
  CONSTRAINT fk_doc_view_logs_doc_id FOREIGN KEY (doc_id) REFERENCES knowledge_doc(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE OR REPLACE VIEW knowledge_docs AS
SELECT
  id,
  title,
  source,
  file_name,
  file_type,
  collection,
  category,
  subcategory,
  metadata_json,
  create_time,
  update_time,
  create_time AS created_at,
  update_time AS updated_at
FROM knowledge_doc;

CREATE OR REPLACE VIEW knowledge_chunks AS
SELECT
  id,
  doc_id,
  chunk_index,
  COALESCE(content, chunk_text) AS content,
  chunk_text,
  score,
  metadata_json,
  create_time,
  update_time,
  create_time AS created_at,
  update_time AS updated_at
FROM knowledge_chunk;

CREATE OR REPLACE VIEW `user` AS
SELECT
  id,
  phone,
  display_name,
  status,
  active_role,
  created_at,
  updated_at
FROM users;
