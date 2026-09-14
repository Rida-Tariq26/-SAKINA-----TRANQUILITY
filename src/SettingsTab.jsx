import { useState } from "react";
import { useAuth } from "./AuthContext";
import { tokens } from "./tokens";
import {
  getStoredApiKey,
  setStoredApiKey,
  removeStoredApiKey,
  getStoredModel,
  setStoredModel,
  SUPPORTED_MODELS,
  verifyApiKey,
  DEFAULT_MODEL,
} from "./apiKeyHelper";

// ─────────────────────────────────────────────
// SETTINGS TAB — Privacy, Security & BYOK API Keys
// ─────────────────────────────────────────────
export default function SettingsTab({ isDark, onNavigate, onLogout }) {
  const t = isDark ? tokens.dark : tokens.light;
  const { user, logout } = useAuth();

  // API Key & Model State
  const [apiKeyInput, setApiKeyInput] = useState(() => getStoredApiKey() || "");
  const [selectedModel, setSelectedModel] = useState(() => getStoredModel() || DEFAULT_MODEL);
  const [showKey, setShowKey] = useState(false);
  const [keyStatus, setKeyStatus] = useState(() => (getStoredApiKey() ? "valid" : "untested"));
  const [keyStatusMsg, setKeyStatusMsg] = useState(() => (getStoredApiKey() ? "Configured in browser storage" : ""));
  const [isVerifying, setIsVerifying] = useState(false);

  // Danger Zone State
  const [deleteStep, setDeleteStep] = useState("idle"); // idle | warn | confirm
  const [deleteInput, setDeleteInput] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deleteLoading, setDelLoading] = useState(false);
  const [exportLoading, setExportLoad] = useState(false);
  const [toast, setToast] = useState("");

  // ── helpers ───────────────────────────────
  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3500);
  };

  const handleSaveAndVerifyKey = async () => {
    const trimmed = apiKeyInput.trim();
    if (!trimmed) {
      removeStoredApiKey();
      setKeyStatus("untested");
      setKeyStatusMsg("");
      showToast("API key removed. Using default server fallback.");
      return;
    }

    setIsVerifying(true);
    setKeyStatus("testing");
    setKeyStatusMsg("Testing connection with Google Gemini...");

    const result = await verifyApiKey(trimmed, selectedModel);
    setIsVerifying(false);

    if (result.valid) {
      setStoredApiKey(trimmed);
      setStoredModel(selectedModel);
      setKeyStatus("valid");
      setKeyStatusMsg(`Active & connected to ${selectedModel}`);
      showToast("✓ Gemini API key verified & saved!");
    } else {
      setKeyStatus("invalid");
      setKeyStatusMsg(result.message);
      showToast("⚠ Key verification failed. Check error below.");
    }
  };

  const handleModelChange = (modelId) => {
    setSelectedModel(modelId);
    setStoredModel(modelId);
    showToast(`Model set to: ${modelId}`);
  };

  const handleRemoveKey = () => {
    removeStoredApiKey();
    setApiKeyInput("");
    setKeyStatus("untested");
    setKeyStatusMsg("");
    showToast("Gemini API key cleared from browser storage.");
  };

  const handleLogout = () => {
    logout();
    onLogout();
  };

  const handleExport = async () => {
    if (!user?.sub) return;
    setExportLoad(true);
    try {
      const res = await fetch("/api/user/data/export", {
        headers: { "X-User-Id": user.sub },
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = `sakina-data-${user.sub.slice(-6)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("Your data has been downloaded.");
    } catch {
      showToast("Export failed — please try again.");
    } finally {
      setExportLoad(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (deleteInput !== "DELETE") {
      setDeleteError("Please type DELETE exactly to confirm.");
      return;
    }
    setDelLoading(true);
    setDeleteError("");
    try {
      const res = await fetch("/api/user/data", {
        method:  "DELETE",
        headers: { "X-User-Id": user.sub },
      });
      if (!res.ok) throw new Error("Deletion failed");
      logout();
      onLogout();
    } catch {
      setDeleteError("Deletion failed — please try again or contact support.");
      setDelLoading(false);
    }
  };

  // ─────────────────────────────────────────
  // SECTION STYLES
  // ─────────────────────────────────────────
  const sectionLabel = {
    fontSize: "0.66rem",
    letterSpacing: "0.14em",
    textTransform: "uppercase",
    color: t.textMuted,
    marginBottom: "0.9rem",
    display: "block",
  };

  const card = {
    background: t.glassCard,
    backdropFilter: "blur(18px)",
    WebkitBackdropFilter: "blur(18px)",
    border: `1px solid ${t.border}`,
    borderRadius: "14px",
    padding: "1.4rem 1.6rem",
    marginBottom: "1rem",
  };

  const actionBtn = (variant = "default") => ({
    background: variant === "danger"
      ? "rgba(220,60,60,0.12)"
      : variant === "primary"
        ? `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`
        : t.glass,
    backdropFilter: "blur(10px)",
    border: variant === "danger"
      ? "1px solid rgba(220,60,60,0.3)"
      : variant === "primary"
        ? "none"
        : `1px solid ${t.border}`,
    borderRadius: "9px",
    padding: "10px 18px",
    cursor: "pointer",
    color: variant === "danger"
      ? "#e07070"
      : variant === "primary"
        ? (isDark ? "#07111C" : "#fff")
        : t.textSecond,
    fontSize: "0.82rem",
    fontFamily: "'Inter', sans-serif",
    transition: "all 0.22s ease",
    display: "flex",
    alignItems: "center",
    gap: "6px",
    fontWeight: variant === "primary" ? 500 : 400,
  });

  const linkBtn = {
    background: "none",
    border: "none",
    color: t.glow,
    fontSize: "0.82rem",
    cursor: "pointer",
    padding: 0,
    fontFamily: "'Inter', sans-serif",
    textDecoration: "underline",
    textDecorationColor: `${t.glow}55`,
  };

  return (
    <div style={{
      padding: "2rem 2.2rem 3rem",
      overflowY: "auto", height: "100%",
      animation: "fadeUp 0.4s ease forwards",
    }}>

      {/* ── ACCOUNT ─────────────────────────── */}
      <span style={sectionLabel}>Account</span>
      <div style={{ ...card, display: "flex", alignItems: "center", gap: "1.2rem" }}>
        {user?.picture
          ? <img src={user.picture} alt={user.name} style={{
              width: "52px", height: "52px", borderRadius: "50%",
              border: `2px solid ${t.border}`, flexShrink: 0,
              objectFit: "cover",
            }} />
          : <div style={{
              width: "52px", height: "52px", borderRadius: "50%",
              background: `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "1.3rem", flexShrink: 0,
            }}>✦</div>
        }
        <div>
          <div style={{ fontWeight: 500, color: t.textPrimary, fontSize: "0.96rem", marginBottom: "2px" }}>
            {user?.name || "Sakina User"}
          </div>
          <div style={{ fontSize: "0.8rem", color: t.textMuted, marginBottom: "4px" }}>
            {user?.email || ""}
          </div>
          <span style={{
            fontSize: "0.68rem",
            letterSpacing: "0.06em",
            color: t.glow,
            background: `${t.glow}18`,
            border: `1px solid ${t.glow}33`,
            borderRadius: "4px",
            padding: "2px 8px",
          }}>Connected via Google</span>
        </div>
      </div>

      {/* ── BRING YOUR OWN KEY (BYOK) ────────── */}
      <span style={{ ...sectionLabel, marginTop: "1.8rem" }}>AI Model & API Key (BYOK)</span>
      <div style={card}>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.1rem" }}>
          
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
              <div style={{ fontSize: "0.92rem", fontWeight: 500, color: t.textPrimary }}>
                Personal Google Gemini API Key
              </div>
              {keyStatus === "valid" && (
                <span style={{
                  fontSize: "0.72rem", color: "#4EBA6F", background: "rgba(78,186,111,0.12)",
                  border: "1px solid rgba(78,186,111,0.3)", borderRadius: "12px", padding: "2px 8px",
                }}>
                  ● Key Active
                </span>
              )}
              {keyStatus === "invalid" && (
                <span style={{
                  fontSize: "0.72rem", color: "#E07070", background: "rgba(224,112,112,0.12)",
                  border: "1px solid rgba(224,112,112,0.3)", borderRadius: "12px", padding: "2px 8px",
                }}>
                  ● Key Issue
                </span>
              )}
            </div>
            <p style={{ fontSize: "0.78rem", color: t.textMuted, lineHeight: 1.55, marginBottom: "0.8rem" }}>
              Provide your own free Google Gemini API key to enjoy uninterrupted personal usage (1,500 free queries/day).
              Your key is stored safely inside your local browser and never exposed.
            </p>
          </div>

          {/* Key Input Field */}
          <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
            <input
              type={showKey ? "text" : "password"}
              value={apiKeyInput}
              onChange={(e) => {
                setApiKeyInput(e.target.value);
                setKeyStatus("untested");
                setKeyStatusMsg("");
              }}
              placeholder="Paste your Gemini API key (AIzaSy...)"
              style={{
                width: "100%",
                background: t.glass,
                border: `1px solid ${
                  keyStatus === "valid"
                    ? "rgba(78,186,111,0.4)"
                    : keyStatus === "invalid"
                    ? "rgba(224,112,112,0.5)"
                    : t.border
                }`,
                borderRadius: "10px",
                padding: "11px 44px 11px 14px",
                color: t.textPrimary,
                fontSize: "0.85rem",
                fontFamily: showKey ? "monospace" : "'Inter', sans-serif",
                outline: "none",
                transition: "border-color 0.2s ease",
              }}
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              style={{
                position: "absolute",
                right: "12px",
                background: "none",
                border: "none",
                cursor: "pointer",
                color: t.textMuted,
                fontSize: "0.82rem",
                padding: "4px",
              }}
              title={showKey ? "Hide key" : "Show key"}
            >
              {showKey ? "🙈" : "👁"}
            </button>
          </div>

          {/* Key Status Message */}
          {keyStatusMsg && (
            <div style={{
              fontSize: "0.78rem",
              color: keyStatus === "valid" ? "#4EBA6F" : keyStatus === "invalid" ? "#E07070" : t.textMuted,
              lineHeight: 1.5,
            }}>
              {keyStatus === "testing" ? "⏳ " : keyStatus === "valid" ? "✓ " : "⚠ "}
              {keyStatusMsg}
            </div>
          )}

          {/* Model Selector */}
          <div style={{ marginTop: "0.4rem" }}>
            <div style={{ fontSize: "0.82rem", color: t.textPrimary, marginBottom: "0.5rem", fontWeight: 500 }}>
              Active AI Model
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {SUPPORTED_MODELS.map((m) => (
                <div
                  key={m.id}
                  onClick={() => handleModelChange(m.id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 14px",
                    borderRadius: "8px",
                    background: selectedModel === m.id ? `${t.glow}15` : t.glass,
                    border: `1px solid ${selectedModel === m.id ? t.borderGlow : t.border}`,
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                  }}
                >
                  <div>
                    <div style={{
                      fontSize: "0.84rem",
                      fontWeight: selectedModel === m.id ? 500 : 400,
                      color: selectedModel === m.id ? t.glow : t.textPrimary,
                    }}>
                      {m.name}
                    </div>
                    <div style={{ fontSize: "0.72rem", color: t.textMuted, marginTop: "2px" }}>
                      {m.description}
                    </div>
                  </div>
                  <input
                    type="radio"
                    name="model"
                    checked={selectedModel === m.id}
                    onChange={() => handleModelChange(m.id)}
                    style={{ accentColor: t.glow }}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", marginTop: "0.3rem" }}>
            <button
              onClick={handleSaveAndVerifyKey}
              disabled={isVerifying || !apiKeyInput.trim()}
              style={actionBtn("primary")}
              onMouseEnter={e => e.currentTarget.style.opacity = "0.9"}
              onMouseLeave={e => e.currentTarget.style.opacity = "1"}
            >
              {isVerifying ? "Verifying…" : "✓ Save & Verify Key"}
            </button>

            {apiKeyInput && (
              <button
                onClick={handleRemoveKey}
                style={actionBtn("default")}
                onMouseEnter={e => { e.currentTarget.style.borderColor = t.borderGlow; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = t.border; }}
              >
                Clear Key
              </button>
            )}

            <a
              href="https://aistudio.google.com/app/apikey"
              target="_blank"
              rel="noreferrer"
              style={{
                ...actionBtn("default"),
                textDecoration: "none",
                marginLeft: "auto",
                color: t.glow,
              }}
            >
              🔑 Get Free API Key (Google AI Studio) ↗
            </a>
          </div>

          {/* Quick Guide */}
          <div style={{
            background: `${t.glow}0C`,
            border: `1px solid ${t.glow}20`,
            borderRadius: "8px",
            padding: "10px 14px",
            fontSize: "0.75rem",
            color: t.textSecond,
            lineHeight: 1.6,
          }}>
            <strong style={{ color: t.glow }}>How to get your free Gemini Key:</strong>
            <ol style={{ paddingLeft: "1.2rem", marginTop: "4px" }}>
              <li>Visit <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" style={{ color: t.glow, textDecoration: "underline" }}>aistudio.google.com/app/apikey</a>.</li>
              <li>Sign in with any Google account and click <strong>Create API Key</strong>.</li>
              <li>Copy the key, paste it in the box above, and click <strong>Save & Verify Key</strong>.</li>
            </ol>
          </div>

        </div>
      </div>

      {/* ── PRIVACY & SECURITY ──────────────── */}
      <span style={{ ...sectionLabel, marginTop: "1.8rem" }}>Privacy & Security</span>

      <div style={card}>
        <div style={{
          display: "flex", flexDirection: "column", gap: "0.9rem",
        }}>
          {/* Download Data */}
          <div style={{
            display: "flex", justifyContent: "space-between",
            alignItems: "center", flexWrap: "wrap", gap: "0.5rem",
          }}>
            <div>
              <div style={{ fontSize: "0.88rem", color: t.textPrimary, marginBottom: "2px" }}>
                Download My Data
              </div>
              <div style={{ fontSize: "0.74rem", color: t.textMuted }}>
                Export all your mood logs and account info as JSON
              </div>
            </div>
            <button
              onClick={handleExport}
              disabled={exportLoading}
              style={actionBtn("default")}
              onMouseEnter={e => { e.currentTarget.style.borderColor = t.borderGlow; e.currentTarget.style.color = t.gold; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = t.border; e.currentTarget.style.color = t.textSecond; }}
            >
              {exportLoading ? "Exporting…" : "⬇ Export"}
            </button>
          </div>

          <div style={{ height: "1px", background: t.border }} />

          {/* Cookie Preferences */}
          <div style={{
            display: "flex", justifyContent: "space-between",
            alignItems: "center", flexWrap: "wrap", gap: "0.5rem",
          }}>
            <div>
              <div style={{ fontSize: "0.88rem", color: t.textPrimary, marginBottom: "2px" }}>
                Cookie Preferences
              </div>
              <div style={{ fontSize: "0.74rem", color: t.textMuted }}>
                Manage what cookies and local storage we use
              </div>
            </div>
            <button
              onClick={() => {
                localStorage.removeItem("sakina_cookie_consent");
                window.location.reload();
              }}
              style={actionBtn("default")}
              onMouseEnter={e => { e.currentTarget.style.borderColor = t.borderGlow; e.currentTarget.style.color = t.gold; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = t.border; e.currentTarget.style.color = t.textSecond; }}
            >🍪 Manage</button>
          </div>

          <div style={{ height: "1px", background: t.border }} />

          {/* Legal Links */}
          <div style={{ display: "flex", gap: "1.2rem", alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontSize: "0.82rem", color: t.textMuted }}>Legal:</span>
            <button style={linkBtn} onClick={() => onNavigate("privacy")}>Privacy Policy</button>
            <button style={linkBtn} onClick={() => onNavigate("terms")}>Terms of Service</button>
          </div>
        </div>
      </div>

      {/* ── DELETE ACCOUNT ──────────────────── */}
      <span style={{ ...sectionLabel, marginTop: "1.8rem" }}>Danger Zone</span>

      {deleteStep === "idle" && (
        <div style={{ ...card, borderColor: "rgba(220,60,60,0.2)" }}>
          <div style={{
            display: "flex", justifyContent: "space-between",
            alignItems: "center", flexWrap: "wrap", gap: "0.8rem",
          }}>
            <div>
              <div style={{ fontSize: "0.88rem", color: "#e07070", marginBottom: "2px", fontWeight: 500 }}>
                Delete Account & Data
              </div>
              <div style={{ fontSize: "0.74rem", color: t.textMuted }}>
                Permanently erases your account and all associated data. This cannot be undone.
              </div>
            </div>
            <button
              onClick={() => setDeleteStep("warn")}
              style={actionBtn("danger")}
            >🗑 Delete Account</button>
          </div>
        </div>
      )}

      {deleteStep === "warn" && (
        <div style={{
          ...card,
          borderColor: "rgba(220,60,60,0.35)",
          background: "rgba(220,60,60,0.06)",
        }}>
          <div style={{ fontSize: "1rem", color: "#e07070", marginBottom: "0.8rem" }}>⚠ Are you sure?</div>
          <p style={{ fontSize: "0.84rem", color: t.textSecond, lineHeight: 1.7, marginBottom: "1.2rem" }}>
            This action is <strong style={{ color: "#e07070" }}>permanent and irreversible</strong>.
            The following will be deleted:
          </p>
          <ul style={{ paddingLeft: "1.3rem", fontSize: "0.82rem", color: t.textMuted, marginBottom: "1.4rem", lineHeight: 1.8 }}>
            <li>Your account profile (name, email, profile picture)</li>
            <li>All mood log entries</li>
            <li>All session history</li>
          </ul>
          <div style={{ display: "flex", gap: "0.6rem" }}>
            <button
              onClick={() => setDeleteStep("idle")}
              style={{ ...actionBtn("default"), flex: 1, justifyContent: "center" }}
            >Cancel</button>
            <button
              onClick={() => setDeleteStep("confirm")}
              style={{ ...actionBtn("danger"), flex: 1, justifyContent: "center" }}
            >Yes, proceed</button>
          </div>
        </div>
      )}

      {deleteStep === "confirm" && (
        <div style={{
          ...card,
          borderColor: "rgba(220,60,60,0.4)",
          background: "rgba(220,60,60,0.06)",
        }}>
          <div style={{ fontSize: "0.88rem", color: "#e07070", marginBottom: "1rem", fontWeight: 500 }}>
            Type <code style={{
              background: "rgba(220,60,60,0.15)", padding: "1px 6px",
              borderRadius: "4px", fontFamily: "monospace",
            }}>DELETE</code> to permanently remove your account
          </div>
          <input
            value={deleteInput}
            onChange={e => { setDeleteInput(e.target.value); setDeleteError(""); }}
            placeholder="Type DELETE here"
            style={{
              width: "100%",
              background: t.glassCard,
              border: `1px solid ${deleteError ? "rgba(220,60,60,0.5)" : t.border}`,
              borderRadius: "9px",
              padding: "10px 14px",
              color: t.textPrimary,
              fontSize: "0.88rem",
              fontFamily: "'Inter', sans-serif",
              outline: "none",
              marginBottom: deleteError ? "0.5rem" : "1rem",
              boxSizing: "border-box",
            }}
          />
          {deleteError && (
            <div style={{ fontSize: "0.78rem", color: "#e07070", marginBottom: "0.8rem" }}>
              {deleteError}
            </div>
          )}
          <div style={{ display: "flex", gap: "0.6rem" }}>
            <button
              onClick={() => { setDeleteStep("idle"); setDeleteInput(""); setDeleteError(""); }}
              style={{ ...actionBtn("default"), flex: 1, justifyContent: "center" }}
              disabled={deleteLoading}
            >Cancel</button>
            <button
              onClick={handleDeleteConfirm}
              disabled={deleteLoading || deleteInput !== "DELETE"}
              style={{
                ...actionBtn("danger"),
                flex: 1, justifyContent: "center",
                opacity: deleteInput === "DELETE" && !deleteLoading ? 1 : 0.45,
              }}
            >{deleteLoading ? "Deleting…" : "Delete Everything"}</button>
          </div>
        </div>
      )}

      {/* ── SIGN OUT ────────────────────────── */}
      <span style={{ ...sectionLabel, marginTop: "1.8rem" }}>Session</span>
      <div style={card}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.8rem" }}>
          <div>
            <div style={{ fontSize: "0.88rem", color: t.textPrimary, marginBottom: "2px" }}>Sign Out</div>
            <div style={{ fontSize: "0.74rem", color: t.textMuted }}>
              Signs you out from this device. Your data is preserved.
            </div>
          </div>
          <button onClick={handleLogout} style={actionBtn("default")}
            onMouseEnter={e => { e.currentTarget.style.borderColor = t.borderGlow; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = t.border; }}
          >Sign Out</button>
        </div>
      </div>

      {/* ── TOAST ───────────────────────────── */}
      {toast && (
        <div style={{
          position: "fixed",
          bottom: "2.5rem", left: "50%",
          transform: "translateX(-50%)",
          background: isDark ? "#0D1B2A" : "#F0E6D4",
          border: `1px solid ${t.borderGlow}`,
          borderRadius: "10px",
          padding: "10px 20px",
          fontSize: "0.82rem",
          color: t.textPrimary,
          boxShadow: t.shadowGlow,
          zIndex: 999,
          animation: "fadeUp 0.3s ease forwards",
          pointerEvents: "none",
          whiteSpace: "nowrap",
        }}>{toast}</div>
      )}
    </div>
  );
}
