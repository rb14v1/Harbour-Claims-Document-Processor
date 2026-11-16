import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteClaim, fetchClaim, generateSummary, uploadDocument, updateClaimStatus } from "../api";
import { useAuth } from "../AuthContext";
import type { Claim, ClaimStatus, DocumentType } from "../types";

export default function ClaimDetail() {
  const { id } = useParams();
  const claimId = Number(id);
  const navigate = useNavigate();
  const { user } = useAuth();

  const [claim, setClaim] = useState<Claim | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [documentType, setDocumentType] = useState<DocumentType>("invoice");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);

  function load() {
    fetchClaim(claimId)
      .then(setClaim)
      .catch(() => setError("Could not load claim."));
  }

  useEffect(load, [claimId]);

  async function handleUpload(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(claimId, file, documentType);
      setFile(null);
      load();
    } catch {
      setError("Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleGenerateSummary() {
    setGenerating(true);
    setError(null);
    try {
      await generateSummary(claimId);
      load();
    } catch {
      setError("Could not generate summary. Add a narrative or document first.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleStatusChange(status: ClaimStatus) {
    setError(null);
    try {
      await updateClaimStatus(claimId, status);
      load();
    } catch {
      setError("Status change rejected (denied claims can only be overridden by an admin).");
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this claim?")) return;
    try {
      await deleteClaim(claimId);
      navigate("/claims");
    } catch {
      setError("Only an admin can delete a claim.");
    }
  }

  if (!claim) {
    return (
      <div>
        {error && <div className="error-banner">{error}</div>}
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div>
      <Link to="/claims">&larr; Back to claims</Link>
      <h2>
        Claim #{claim.id} - {claim.claimant_name}
      </h2>
      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <p>
          Policy: <strong>{claim.policy_number}</strong> | Type: <strong>{claim.claim_type}</strong> | Status:{" "}
          <span className={`badge badge-${claim.status}`}>{claim.status}</span>
        </p>
        <div className="form-grid" style={{ gridTemplateColumns: "repeat(4, auto)", display: "flex", gap: "0.5rem" }}>
          {(["submitted", "under_review", "approved", "denied"] as ClaimStatus[]).map((s) => (
            <button
              key={s}
              className="secondary"
              disabled={s === claim.status}
              onClick={() => handleStatusChange(s)}
            >
              {s}
            </button>
          ))}
          {user?.role === "admin" && (
            <button className="danger" onClick={handleDelete}>
              Delete claim
            </button>
          )}
        </div>
      </div>

      <div className="card">
        <h3>Documents</h3>
        <form onSubmit={handleUpload} className="form-grid">
          <label>
            Document type
            <select value={documentType} onChange={(e) => setDocumentType(e.target.value as DocumentType)}>
              <option value="invoice">Invoice</option>
              <option value="police_report">Police Report</option>
              <option value="medical_bill">Medical Bill</option>
              <option value="photo">Photo</option>
            </select>
          </label>
          <label>
            File
            <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <button type="submit" disabled={!file || uploading}>
            {uploading ? "Uploading..." : "Upload document"}
          </button>
        </form>

        <table className="claims-table" style={{ marginTop: "1rem" }}>
          <thead>
            <tr>
              <th>Type</th>
              <th>Vendor</th>
              <th>Amount</th>
              <th>Date</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {claim.documents.map((doc) => (
              <tr key={doc.id}>
                <td>{doc.document_type}</td>
                <td>{doc.extracted_fields.vendor}</td>
                <td>{doc.extracted_fields.amount}</td>
                <td>{doc.extracted_fields.date}</td>
                <td>{doc.extracted_fields.description}</td>
              </tr>
            ))}
            {claim.documents.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  No documents uploaded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>AI Summary</h3>
        <button onClick={handleGenerateSummary} disabled={generating}>
          {generating ? "Generating..." : "Generate / Refresh Summary"}
        </button>
        {claim.summary ? (
          <div style={{ marginTop: "1rem" }}>
            {claim.summary.flagged_for_review && (
              <div className="flagged">⚠ Flagged for review - possible duplicate/fraud pattern</div>
            )}
            <p>{claim.summary.ai_summary_text}</p>
            {claim.summary.similar_claim_ids.length > 0 && (
              <p className="muted">Similar claim IDs: {claim.summary.similar_claim_ids.join(", ")}</p>
            )}
          </div>
        ) : (
          <p className="muted">No summary generated yet.</p>
        )}
      </div>
    </div>
  );
}
