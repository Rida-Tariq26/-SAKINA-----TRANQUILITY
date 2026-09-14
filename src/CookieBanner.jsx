import { useState } from "react";
import { tokens } from "./tokens";

// ─────────────────────────────────────────────
// COOKIE BANNER  (GDPR / CCPA compliant)
// ─────────────────────────────────────────────

const STORAGE_KEY    = "sakina_cookie_consent";
const DEFAULT_PREFS  = { essential: true, functional: false, analytics: false };

function loadPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function savePrefs(prefs) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
}

// ── Customize Modal ──────────────────────────
function CustomizeModal({ isDark, prefs, onSave, onClose }) {
  const t = isDark ? tokens.dark : tokens.light;
  const [local, setLocal] = useState({ ...prefs });

  const categories = [
    {
      key:   "essential",
      label: "Essential",
      desc:  "Required for the app to function — login session, security, language. Cannot be disabled.",
      locked: true,
    },
    {
      key:   "functional",
      label: "Functional",
      desc:  "Remembers your preferences such as theme, language mode, and Dhikr settings.",
      locked: false,
    },
    {
      key:   "analytics",
      label: "Analytics",
      desc:  "Helps us understand how Sakina is used so we can improve it. No personal data is shared with third parties.",
      locked: false,
    },
  ];

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(0,0,0,0.55)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: "1rem",
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{
        width: "100%", maxWidth: "460px",
        background: isDark ? "#0D1B2A" : "#F0E6D4",
        border: `1px solid ${t.border}`,
        borderRadius: "16px",
        padding: "2rem",
        boxShadow: t.shadow,
      }}>
        <h2 style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontSize: "1.4rem", fontWeight: 400,
          color: t.textPrimary, marginBottom: "0.4rem",
        }}>Cookie Preferences</h2>
        <p style={{ fontSize: "0.8rem", color: t.textMuted, marginBottom: "1.6rem", lineHeight: 1.6 }}>
          Manage which cookies Sakina uses. Essential cookies are always active.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {categories.map(cat => (
            <div key={cat.key} style={{
              display: "flex", alignItems: "flex-start", gap: "1rem",
              padding: "1rem",
              background: t.glass,
              border: `1px solid ${t.border}`,
              borderRadius: "10px",
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: "0.88rem", fontWeight: 500, color: t.textPrimary, marginBottom: "0.3rem" }}>
                  {cat.label}
                </div>
                <div style={{ fontSize: "0.76rem", color: t.textMuted, lineHeight: 1.55 }}>
                  {cat.desc}
                </div>
              </div>
              {/* Toggle */}
              <div
                onClick={() => !cat.locked && setLocal(p => ({ ...p, [cat.key]: !p[cat.key] }))}
                style={{
                  width: "40px", height: "22px", flexShrink: 0,
                  borderRadius: "11px",
                  background: local[cat.key] ? t.glow : t.border,
                  position: "relative",
                  cursor: cat.locked ? "default" : "pointer",
                  transition: "background 0.25s ease",
                  opacity: cat.locked ? 0.6 : 1,
                  marginTop: "2px",
                }}
              >
                <div style={{
                  position: "absolute",
                  top: "3px",
                  left: local[cat.key] ? "21px" : "3px",
                  width: "16px", height: "16px",
                  borderRadius: "50%",
                  background: "#fff",
                  transition: "left 0.2s ease",
                  boxShadow: "0 1px 4px rgba(0,0,0,0.2)",
                }} />
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", gap: "0.75rem", marginTop: "1.6rem", justifyContent: "flex-end" }}>
          <button onClick={onClose} style={{
            background: "transparent",
            border: `1px solid ${t.border}`,
            borderRadius: "8px",
            padding: "9px 18px",
            color: t.textMuted, fontSize: "0.8rem",
            cursor: "pointer",
          }}>Cancel</button>
          <button onClick={() => onSave(local)} style={{
            background: `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`,
            border: "none", borderRadius: "8px",
            padding: "9px 18px",
            color: isDark ? "#07111C" : "#fff",
            fontSize: "0.8rem", fontWeight: 500,
            cursor: "pointer",
          }}>Save Preferences</button>
        </div>
      </div>
    </div>
  );
}

// ── Main Banner Component ────────────────────
export default function CookieBanner({ isDark }) {
  const t = isDark ? tokens.dark : tokens.light;
  const [prefs, setPrefs] = useState(() => loadPrefs()); // null = not yet decided
  const [showCustom, setCustom] = useState(false);
  const [showFab, setShowFab] = useState(() => Boolean(loadPrefs()));

  const accept = (chosenPrefs) => {
    savePrefs(chosenPrefs);
    setPrefs(chosenPrefs);
    setShowFab(true);
    setCustom(false);
  };

  const acceptAll  = () => accept({ essential: true, functional: true,  analytics: true  });
  const rejectNonE = () => accept({ ...DEFAULT_PREFS });

  // Banner only shown before user makes a choice
  const showBanner = prefs === null;

  return (
    <>
      {/* ── Cookie Consent Banner ────────────── */}
      {showBanner && (
        <div role="dialog" aria-label="Cookie consent" style={{
          position: "fixed",
          bottom: "1.5rem", left: "50%",
          transform: "translateX(-50%)",
          width: "min(680px, calc(100vw - 2rem))",
          zIndex: 900,
          background: isDark ? "rgba(13,27,42,0.97)" : "rgba(255,253,248,0.97)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          border: `1px solid ${t.border}`,
          borderRadius: "16px",
          padding: "1.4rem 1.6rem",
          boxShadow: t.shadow,
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
        }}>
          <div style={{ display: "flex", gap: "0.7rem", alignItems: "flex-start" }}>
            <span style={{ fontSize: "1.1rem", flexShrink: 0, marginTop: "1px" }}>🍪</span>
            <div>
              <p style={{ fontSize: "0.85rem", color: t.textPrimary, lineHeight: 1.65, margin: 0 }}>
                <strong style={{ color: t.gold }}>Sakina uses cookies</strong> to keep you signed in and improve your experience.
                We never sell your data. You can{" "}
                <button onClick={() => setCustom(true)} style={{
                  background: "none", border: "none",
                  color: t.glow, cursor: "pointer",
                  fontSize: "inherit", padding: 0, textDecoration: "underline",
                }}>customize your preferences</button>
                {" "}or read our{" "}
                <a href="#privacy" onClick={e => { e.preventDefault(); }} style={{ color: t.glow }}>
                  Privacy Policy
                </a>.
              </p>
            </div>
          </div>

          <div style={{
            display: "flex", gap: "0.6rem", flexWrap: "wrap", justifyContent: "flex-end",
          }}>
            <button onClick={() => setCustom(true)} style={{
              background: "transparent",
              border: `1px solid ${t.border}`,
              borderRadius: "8px",
              padding: "9px 16px",
              color: t.textMuted, fontSize: "0.78rem",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}>Customize</button>

            <button onClick={rejectNonE} style={{
              background: "transparent",
              border: `1px solid ${t.border}`,
              borderRadius: "8px",
              padding: "9px 16px",
              color: t.textSecond, fontSize: "0.78rem",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}>Reject Non-Essential</button>

            <button onClick={acceptAll} style={{
              background: `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`,
              border: "none",
              borderRadius: "8px",
              padding: "9px 20px",
              color: isDark ? "#07111C" : "#fff",
              fontSize: "0.78rem", fontWeight: 500,
              cursor: "pointer",
              whiteSpace: "nowrap",
              boxShadow: `0 4px 14px rgba(196,132,90,0.3)`,
            }}>Accept All</button>
          </div>
        </div>
      )}

      {/* ── Cookie Preferences FAB ─────────── */}
      {showFab && !showBanner && (
        <button
          title="Cookie Preferences"
          onClick={() => setCustom(true)}
          style={{
            position: "fixed",
            bottom: "1.5rem", left: "1.5rem",
            zIndex: 800,
            width: "38px", height: "38px",
            borderRadius: "50%",
            background: t.glass,
            backdropFilter: "blur(12px)",
            border: `1px solid ${t.border}`,
            cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "1rem",
            color: t.textMuted,
            transition: "all 0.22s ease",
            boxShadow: t.shadow,
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = t.borderGlow; e.currentTarget.style.color = t.glow; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = t.border; e.currentTarget.style.color = t.textMuted; }}
        >🍪</button>
      )}

      {/* ── Customize Modal ─────────────────── */}
      {showCustom && (
        <CustomizeModal
          isDark={isDark}
          prefs={prefs || DEFAULT_PREFS}
          onSave={accept}
          onClose={() => setCustom(false)}
        />
      )}
    </>
  );
}
