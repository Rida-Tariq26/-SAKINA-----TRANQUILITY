import { useState } from "react";
import { GoogleLogin } from "@react-oauth/google";
import { useAuth } from "./AuthContext";
import { tokens } from "./tokens";   // we'll re-export tokens from a shared file

// ─────────────────────────────────────────────
// GOOGLE SIGN-IN PAGE
// ─────────────────────────────────────────────
export default function GoogleSignIn({ isDark, onSuccess, onBack, onNavigate }) {
  const t = isDark ? tokens.dark : tokens.light;
  const { login } = useAuth();

  const [termsAccepted, setTermsAccepted] = useState(false);
  const [error, setError]                 = useState("");
  const [busy, setBusy]                   = useState(false);

  const handleCredential = async (credentialResponse) => {
    if (!termsAccepted) {
      setError("Please accept the Terms of Service to continue.");
      return;
    }
    setBusy(true);
    setError("");
    const { ok, error: loginError } = await login(credentialResponse.credential);
    setBusy(false);
    if (ok) {
      onSuccess();
    } else {
      setError(loginError || "Sign-in failed. Please try again.");
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      background: t.bgBase,
      padding: "2rem",
      position: "relative",
    }}>
      {/* Background gradient blob */}
      <div style={{
        position: "absolute",
        top: "50%", left: "50%",
        transform: "translate(-50%,-60%)",
        width: "600px", height: "600px",
        borderRadius: "50%",
        background: isDark
          ? "radial-gradient(circle, rgba(196,132,90,0.08) 0%, transparent 65%)"
          : "radial-gradient(circle, rgba(160,98,60,0.07) 0%, transparent 65%)",
        pointerEvents: "none",
      }} />

      {/* Card */}
      <div style={{
        width: "100%",
        maxWidth: "420px",
        background: t.glassCard,
        backdropFilter: "blur(24px) saturate(1.5)",
        WebkitBackdropFilter: "blur(24px) saturate(1.5)",
        border: `1px solid ${t.border}`,
        borderRadius: "20px",
        padding: "3rem 2.5rem",
        boxShadow: t.shadow,
        position: "relative",
        zIndex: 1,
        textAlign: "center",
      }}>
        {/* Logo */}
        <div style={{
          width: "56px", height: "56px",
          borderRadius: "50%",
          background: `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "1.6rem", margin: "0 auto 1.2rem",
          boxShadow: `0 0 28px rgba(196,132,90,0.3)`,
        }}>✦</div>

        <h1 style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontWeight: 300,
          fontSize: "2rem",
          color: t.textPrimary,
          letterSpacing: "0.14em",
          marginBottom: "0.4rem",
        }}>Sakina</h1>

        <p style={{
          fontSize: "0.82rem",
          color: t.textMuted,
          letterSpacing: "0.05em",
          marginBottom: "2.2rem",
          lineHeight: 1.6,
        }}>
          A guided space for psychological & spiritual tranquility
        </p>

        {/* Divider */}
        <div style={{
          width: "40px", height: "1px",
          background: `linear-gradient(90deg, transparent, ${t.glow}, transparent)`,
          margin: "0 auto 2rem",
        }} />

        {/* Terms checkbox */}
        <div style={{
          display: "flex",
          alignItems: "flex-start",
          gap: "10px",
          marginBottom: "1.6rem",
          textAlign: "left",
        }}>
          <button
            type="button"
            role="checkbox"
            aria-checked={termsAccepted}
            aria-label="Agree to Terms of Service and Privacy Policy"
            style={{
              width: "18px",
              height: "18px",
              flexShrink: 0,
              borderRadius: "4px",
              border: `1.5px solid ${termsAccepted ? t.glow : t.border}`,
              background: termsAccepted ? `${t.glow}22` : "transparent",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.2s ease",
              marginTop: "1px",
              cursor: "pointer",
              padding: 0,
            }}
            onClick={() => setTermsAccepted(v => !v)}
          >
            {termsAccepted && (
              <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                <path d="M1 4l3 3 5-6" stroke={t.glow} strokeWidth="1.8"
                  strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
          </button>
          <span style={{ fontSize: "0.78rem", color: t.textSecond, lineHeight: 1.65 }}>
            <span
              onClick={() => setTermsAccepted(v => !v)}
              style={{ cursor: "pointer", userSelect: "none" }}
            >
              I agree to Sakina's{" "}
            </span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onNavigate("terms");
              }}
              style={{
                background: "none", border: "none", padding: 0,
                color: t.glow, fontSize: "inherit", cursor: "pointer",
                textDecoration: "underline",
              }}
            >Terms of Service</button>{" "}and{" "}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onNavigate("privacy");
              }}
              style={{
                background: "none", border: "none", padding: 0,
                color: t.glow, fontSize: "inherit", cursor: "pointer",
                textDecoration: "underline",
              }}
            >Privacy Policy</button>
          </span>
        </div>

        {/* Error message */}
        {error && (
          <div style={{
            background: "rgba(220,60,60,0.12)",
            border: "1px solid rgba(220,60,60,0.3)",
            borderRadius: "8px",
            padding: "10px 14px",
            marginBottom: "1.2rem",
            fontSize: "0.8rem",
            color: "#e07070",
            textAlign: "left",
          }}>{error}</div>
        )}

        {/* Google Login Button */}
        <div style={{
          opacity: termsAccepted && !busy ? 1 : 0.45,
          pointerEvents: termsAccepted && !busy ? "auto" : "none",
          transition: "opacity 0.25s ease",
          display: "flex",
          justifyContent: "center",
        }}>
          <GoogleLogin
            onSuccess={handleCredential}
            onError={() => setError("Google Sign-In failed. Please try again.")}
            theme={isDark ? "filled_black" : "outline"}
            shape="rectangular"
            size="large"
            text="continue_with"
            useOneTap={false}
          />
        </div>

        {busy && (
          <p style={{ marginTop: "1rem", fontSize: "0.78rem", color: t.textMuted }}>
            Verifying…
          </p>
        )}

        {/* Back link */}
        <button onClick={onBack} style={{
          background: "none", border: "none",
          color: t.textMuted, fontSize: "0.75rem",
          cursor: "pointer", marginTop: "1.8rem",
          letterSpacing: "0.05em",
          transition: "color 0.2s",
        }}
          onMouseEnter={e => e.currentTarget.style.color = t.glow}
          onMouseLeave={e => e.currentTarget.style.color = t.textMuted}
        >← Back to home</button>
      </div>

      {/* Footer */}
      <div style={{
        marginTop: "2rem",
        display: "flex", gap: "1.5rem",
        fontSize: "0.72rem", color: t.textMuted,
      }}>
        <button onClick={() => onNavigate("privacy")} style={{
          background: "none", border: "none",
          color: "inherit", cursor: "pointer", fontSize: "inherit",
          transition: "color 0.2s",
        }}
          onMouseEnter={e => e.currentTarget.style.color = t.glow}
          onMouseLeave={e => e.currentTarget.style.color = t.textMuted}
        >Privacy Policy</button>
        <span>·</span>
        <button onClick={() => onNavigate("terms")} style={{
          background: "none", border: "none",
          color: "inherit", cursor: "pointer", fontSize: "inherit",
          transition: "color 0.2s",
        }}
          onMouseEnter={e => e.currentTarget.style.color = t.glow}
          onMouseLeave={e => e.currentTarget.style.color = t.textMuted}
        >Terms of Service</button>
      </div>
    </div>
  );
}
