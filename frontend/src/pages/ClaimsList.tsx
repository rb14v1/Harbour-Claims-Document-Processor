import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createClaim, fetchClaims } from "../api";
import type { Claim, ClaimType } from "../types";

const STATUS_LABEL: Record<string, string> = {
  submitted: "Submitted",
  under_review: "Under Review",
  approved: "Approved",
  denied: "Denied",
};

export default function ClaimsList() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const [claimantName, setClaimantName] = useState("");
  const [policyNumber, setPolicyNumber] = useState("");
  const [claimType, setClaimType] = useState<ClaimType>("auto");
  const [narrativeText, setNarrativeText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function load() {
    setLoading(true);
    fetchClaims()
      .then((data) => setClaims(data.results))
      .catch(() => setError("Could not load claims."))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createClaim({
        claimant_name: claimantName,
        policy_number: policyNumber,
        claim_type: claimType,
        narrative_text: narrativeText || undefined,
      });
      setClaimantName("");
      setPolicyNumber("");
      setNarrativeText("");
      setShowForm(false);
      load();
    } catch {
      setError("Could not create claim. Check the fields and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Claims</h2>
        <button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New Claim"}</button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {showForm && (
        <form className="card form-grid" onSubmit={handleCreate}>
          <label>
            Claimant name
            <input value={claimantName} onChange={(e) => setClaimantName(e.target.value)} required />
          </label>
          <label>
            Policy number
            <input value={policyNumber} onChange={(e) => setPolicyNumber(e.target.value)} required />
          </label>
          <label>
            Claim type
            <select value={claimType} onChange={(e) => setClaimType(e.target.value as ClaimType)}>
              <option value="auto">Auto</option>
              <option value="property">Property</option>
              <option value="medical">Medical</option>
            </select>
          </label>
          <label>
            Narrative (optional, used for similarity search)
            <textarea
              value={narrativeText}
              onChange={(e) => setNarrativeText(e.target.value)}
              rows={3}
            />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? "Creating..." : "Create Claim"}
          </button>
        </form>
      )}

      {loading ? (
        <p>Loading...</p>
      ) : (
        <table className="claims-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Claimant</th>
              <th>Policy #</th>
              <th>Type</th>
              <th>Status</th>
              <th>Flagged</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((c) => (
              <tr key={c.id}>
                <td>
                  <Link to={`/claims/${c.id}`}>#{c.id}</Link>
                </td>
                <td>{c.claimant_name}</td>
                <td>{c.policy_number}</td>
                <td>{c.claim_type}</td>
                <td>
                  <span className={`badge badge-${c.status}`}>{STATUS_LABEL[c.status]}</span>
                </td>
                <td>{c.summary?.flagged_for_review ? "⚠ Yes" : "-"}</td>
              </tr>
            ))}
            {claims.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  No claims yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
