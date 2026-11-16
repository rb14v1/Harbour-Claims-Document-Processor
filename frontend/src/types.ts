export type ClaimType = "auto" | "property" | "medical";
export type ClaimStatus = "submitted" | "under_review" | "approved" | "denied";
export type DocumentType = "invoice" | "police_report" | "medical_bill" | "photo";
export type UserRole = "adjuster" | "admin";

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
}

export interface ExtractedFields {
  vendor?: string;
  amount?: number;
  date?: string;
  description?: string;
}

export interface ClaimDocument {
  id: number;
  claim: number;
  document_type: DocumentType;
  blob_path: string;
  extracted_fields: ExtractedFields;
  uploaded_at: string;
}

export interface ClaimSummary {
  id: number;
  claim: number;
  ai_summary_text: string;
  flagged_for_review: boolean;
  similar_claim_ids: number[];
  generated_at: string;
}

export interface Claim {
  id: number;
  claimant_name: string;
  policy_number: string;
  claim_type: ClaimType;
  status: ClaimStatus;
  submitted_by: number;
  submitted_by_email: string;
  created_at: string;
  updated_at: string;
  documents: ClaimDocument[];
  summary: ClaimSummary | null;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
