import { tokens } from "./tokens";

// ─────────────────────────────────────────────
// SHARED LEGAL PAGE SHELL
// ─────────────────────────────────────────────
function LegalPage({ isDark, title, onBack, children }) {
  const t = isDark ? tokens.dark : tokens.light;

  return (
    <div style={{
      minHeight: "100vh",
      background: t.bgBase,
      color: t.textPrimary,
      fontFamily: "'Inter', sans-serif",
    }}>
      {/* Sticky header */}
      <div style={{
        position: "sticky", top: 0, zIndex: 10,
        background: isDark ? "rgba(7,17,28,0.92)" : "rgba(232,220,203,0.92)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        borderBottom: `1px solid ${t.border}`,
        padding: "1rem 2rem",
        display: "flex", alignItems: "center", gap: "1rem",
      }}>
        <button onClick={onBack} style={{
          background: "transparent",
          border: `1px solid ${t.border}`,
          borderRadius: "8px",
          padding: "6px 14px",
          color: t.textMuted, fontSize: "0.78rem",
          cursor: "pointer", letterSpacing: "0.04em",
          transition: "all 0.2s",
        }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = t.borderGlow; e.currentTarget.style.color = t.glow; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = t.border; e.currentTarget.style.color = t.textMuted; }}
        >← Back</button>
        <span style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontSize: "1.1rem", fontWeight: 400,
          color: t.textPrimary, letterSpacing: "0.1em",
        }}>✦ {title}</span>
      </div>

      {/* Body */}
      <div style={{
        maxWidth: "760px",
        margin: "0 auto",
        padding: "3rem 2rem 5rem",
      }}>
        {children}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────
function Section({ t, title, children }) {
  return (
    <section style={{ marginBottom: "2.4rem" }}>
      <h2 style={{
        fontSize: "1rem",
        fontWeight: 500,
        color: t.gold,
        letterSpacing: "0.08em",
        marginBottom: "0.8rem",
        paddingBottom: "0.5rem",
        borderBottom: `1px solid ${t.border}`,
      }}>{title}</h2>
      <div style={{ fontSize: "0.88rem", lineHeight: 1.85, color: t.textSecond }}>
        {children}
      </div>
    </section>
  );
}

function P({ children, style }) {
  return <p style={{ marginBottom: "0.9rem", ...style }}>{children}</p>;
}

function Ul({ items }) {
  return (
    <ul style={{ paddingLeft: "1.4rem", marginBottom: "0.9rem" }}>
      {items.map((item, i) => (
        <li key={i} style={{ marginBottom: "0.4rem" }}>{item}</li>
      ))}
    </ul>
  );
}

// ─────────────────────────────────────────────
// PRIVACY POLICY PAGE
// ─────────────────────────────────────────────
export default function PrivacyPolicy({ isDark, onBack }) {
  const t = isDark ? tokens.dark : tokens.light;

  return (
    <LegalPage isDark={isDark} title="Privacy Policy" onBack={onBack}>
      {/* Header */}
      <div style={{ marginBottom: "3rem" }}>
        <h1 style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontSize: "2.4rem", fontWeight: 300,
          color: t.textPrimary, letterSpacing: "0.1em",
          marginBottom: "0.6rem",
        }}>Privacy Policy</h1>
        <p style={{ fontSize: "0.78rem", color: t.textMuted }}>
          Effective date: 9 September 2026 · Sakina Wellness App
        </p>
      </div>

      <Section t={t} title="1. Introduction">
        <P>
          Sakina ("we", "our", or "us") is a digital wellness companion that provides guided
          conversations, Dhikr & Duʿāʾ practice, and mood tracking. We are deeply committed to
          protecting your privacy and handling your personal data with transparency and care.
        </P>
        <P>
          This Privacy Policy explains what personal data we collect, why we collect it, how we
          use it, and the rights you have under the General Data Protection Regulation (GDPR),
          California Consumer Privacy Act (CCPA), and other applicable privacy laws.
        </P>
      </Section>

      <Section t={t} title="2. Data We Collect">
        <P><strong style={{ color: t.textPrimary }}>Account Information (via Google Sign-In)</strong></P>
        <Ul t={t} items={[
          "Your Google account name and email address",
          "Your Google profile picture URL",
          "A pseudonymous user identifier (your Google 'sub' ID)",
        ]} />

        <P><strong style={{ color: t.textPrimary }}>App Usage Data</strong></P>
        <Ul t={t} items={[
          "Mood entries you log (emotional state, intensity, optional notes)",
          "Timestamps of when you use the app",
          "Your selected mode (Islamic / Clinical & Scientific) and theme preference",
        ]} />

        <P><strong style={{ color: t.textPrimary }}>Technical Data (Essential Cookies only)</strong></P>
        <Ul t={t} items={[
          "Authentication tokens stored in your browser's localStorage",
          "Your cookie consent preferences",
        ]} />

        <P>
          We do <strong style={{ color: t.textPrimary }}>not</strong> collect your location, contact
          list, financial information, or any data from other applications on your device.
        </P>
      </Section>

      <Section t={t} title="3. How We Use Your Data">
        <Ul t={t} items={[
          "To authenticate you securely via Google OAuth 2.0",
          "To personalise your experience (e.g., recommending relevant Dhikr for your logged mood)",
          "To display your mood history and trends on the Mood Tracker dashboard",
          "To comply with our legal obligations",
        ]} />
      </Section>

      <Section t={t} title="4. Third-Party Services">
        <P>
          <strong style={{ color: t.textPrimary }}>Google Identity Services</strong> — We use
          Google's OAuth 2.0 for authentication. When you sign in, Google processes your login
          credentials according to{" "}
          <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer"
            style={{ color: t.glow }}>Google's Privacy Policy</a>.
        </P>
        <P>
          <strong style={{ color: t.textPrimary }}>Google Gemini API</strong> — Your conversation
          messages and mood inputs are sent to Google's Gemini API to generate responses.
          Google processes these in accordance with their{" "}
          <a href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noopener noreferrer"
            style={{ color: t.glow }}>API Terms of Service</a>.
          We do not store the content of your chat conversations on our servers beyond the
          current session.
        </P>
      </Section>

      <Section t={t} title="5. Data Retention">
        <P>
          Your mood log data is retained for as long as your account is active. You may delete
          your account and all associated data at any time via <em>Settings → Delete Account & Data</em>.
          Upon deletion, your personal data is permanently erased and your account record is
          anonymised within 30 days.
        </P>
      </Section>

      <Section t={t} title="6. Your Rights (GDPR / CCPA)">
        <P>Depending on your jurisdiction, you have the right to:</P>
        <Ul t={t} items={[
          "Access — request a copy of the personal data we hold about you",
          "Rectification — correct inaccurate data",
          "Erasure — request deletion of your personal data ('right to be forgotten')",
          "Data portability — export your data in a machine-readable format",
          "Restriction — limit how we process your data in certain circumstances",
          "Objection — object to processing based on legitimate interests",
          "Opt-out of sale (CCPA) — we do not sell your personal data",
        ]} />
        <P>
          You can exercise the Access, Erasure, and Portability rights directly within the app
          via <em>Settings → Privacy & Security</em>. For other requests, contact us at the
          address below.
        </P>
      </Section>

      <Section t={t} title="7. Cookies">
        <P>
          We use browser localStorage (functionally equivalent to cookies) for three purposes:
        </P>
        <Ul t={t} items={[
          "Essential: keep you signed in and store your consent choices",
          "Functional: remember your theme and language preferences",
          "Analytics: understand aggregate usage patterns (no third-party trackers)",
        ]} />
        <P>
          You can manage your cookie preferences at any time via the 🍪 button visible in
          the bottom-left corner of the app.
        </P>
      </Section>

      <Section t={t} title="8. Security">
        <P>
          We implement industry-standard security practices: Google ID tokens are verified
          server-side on every login, data is stored in a protected SQLite database, and
          all traffic is served over HTTPS in production. No system is completely immune to
          threats; we encourage you not to share your login credentials with others.
        </P>
      </Section>

      <Section t={t} title="9. Children's Privacy">
        <P>
          Sakina is not directed at children under the age of 13. We do not knowingly collect
          personal information from children. If you believe a child has provided us with
          personal information, please contact us immediately.
        </P>
      </Section>

      <Section t={t} title="10. Changes to This Policy">
        <P>
          We may update this Privacy Policy from time to time. Material changes will be
          communicated via an in-app notice. Continued use of Sakina after the effective date
          constitutes acceptance of the updated policy.
        </P>
      </Section>

      <Section t={t} title="11. Contact Us">
        <P>
          If you have any questions or wish to exercise your privacy rights, please contact
          us at: <span style={{ color: t.glow }}>privacy@sakina.app</span>
        </P>
      </Section>
    </LegalPage>
  );
}
