import { tokens } from "./tokens";

// ─────────────────────────────────────────────
// SHARED LEGAL PAGE SHELL (copied from PrivacyPolicy for independence)
// ─────────────────────────────────────────────
function LegalPage({ isDark, title, onBack, children }) {
  const t = isDark ? tokens.dark : tokens.light;
  return (
    <div style={{ minHeight: "100vh", background: t.bgBase, color: t.textPrimary, fontFamily: "'Inter', sans-serif" }}>
      <div style={{
        position: "sticky", top: 0, zIndex: 10,
        background: isDark ? "rgba(7,17,28,0.92)" : "rgba(232,220,203,0.92)",
        backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)",
        borderBottom: `1px solid ${t.border}`,
        padding: "1rem 2rem",
        display: "flex", alignItems: "center", gap: "1rem",
      }}>
        <button onClick={onBack} style={{
          background: "transparent", border: `1px solid ${t.border}`,
          borderRadius: "8px", padding: "6px 14px",
          color: t.textMuted, fontSize: "0.78rem", cursor: "pointer",
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
      <div style={{ maxWidth: "760px", margin: "0 auto", padding: "3rem 2rem 5rem" }}>
        {children}
      </div>
    </div>
  );
}

function Section({ t, title, children }) {
  return (
    <section style={{ marginBottom: "2.4rem" }}>
      <h2 style={{
        fontSize: "1rem", fontWeight: 500, color: t.gold,
        letterSpacing: "0.08em", marginBottom: "0.8rem",
        paddingBottom: "0.5rem", borderBottom: `1px solid ${t.border}`,
      }}>{title}</h2>
      <div style={{ fontSize: "0.88rem", lineHeight: 1.85, color: t.textSecond }}>
        {children}
      </div>
    </section>
  );
}
function P({ children }) { return <p style={{ marginBottom: "0.9rem" }}>{children}</p>; }
function Ul({ items }) {
  return (
    <ul style={{ paddingLeft: "1.4rem", marginBottom: "0.9rem" }}>
      {items.map((item, i) => <li key={i} style={{ marginBottom: "0.4rem" }}>{item}</li>)}
    </ul>
  );
}

// ─────────────────────────────────────────────
// TERMS OF SERVICE PAGE
// ─────────────────────────────────────────────
export default function TermsOfService({ isDark, onBack }) {
  const t = isDark ? tokens.dark : tokens.light;

  return (
    <LegalPage isDark={isDark} title="Terms of Service" onBack={onBack}>
      {/* Header */}
      <div style={{ marginBottom: "3rem" }}>
        <h1 style={{
          fontFamily: "'Cormorant Garamond', serif",
          fontSize: "2.4rem", fontWeight: 300,
          color: t.textPrimary, letterSpacing: "0.1em", marginBottom: "0.6rem",
        }}>Terms of Service</h1>
        <p style={{ fontSize: "0.78rem", color: t.textMuted }}>
          Effective date: 9 September 2026 · Sakina Wellness App
        </p>
      </div>

      <Section t={t} title="1. Acceptance of Terms">
        <P>
          By creating an account or using the Sakina application ("Service"), you agree to be
          bound by these Terms of Service ("Terms"). If you do not agree to these Terms, please
          do not use the Service.
        </P>
        <P>
          These Terms govern your use of Sakina and form a legally binding agreement between
          you and Sakina ("we", "us", or "our").
        </P>
      </Section>

      <Section t={t} title="2. Description of the Service">
        <P>
          Sakina is a digital wellness companion that provides:
        </P>
        <Ul items={[
          "AI-powered guided conversations for psychological and spiritual support",
          "Dhikr (Islamic remembrance) and evidence-based mindfulness practices",
          "A mood tracking and journalling tool",
        ]} />
        <P>
          The Service is intended to complement — not replace — professional mental health care.
          See Section 4 for the important medical disclaimer.
        </P>
      </Section>

      <Section t={t} title="3. Eligibility">
        <Ul items={[
          "You must be at least 13 years old to use the Service.",
          "By using the Service, you represent that you meet this age requirement.",
          "If you are under 18, you must have parental or guardian consent.",
        ]} />
      </Section>

      <Section t={t} title="4. Medical & Mental Health Disclaimer">
        <P>
          <strong style={{ color: t.textPrimary }}>Sakina is NOT a medical device, clinical
          service, or licensed mental health provider.</strong> The conversations, practices,
          and content within the Service are for informational and spiritual support purposes only.
        </P>
        <P>
          Sakina does not provide diagnosis, treatment, or medical advice. If you are
          experiencing a mental health crisis, suicidal thoughts, or any medical emergency,
          please contact a licensed mental health professional or emergency services immediately.
        </P>
        <P>
          In Pakistan: Umang helpline <strong style={{ color: t.gold }}>0317-4288665</strong>.
          Internationally: consult your local emergency services.
        </P>
      </Section>

      <Section t={t} title="5. User Accounts">
        <Ul items={[
          "You are responsible for maintaining the security of your Google account.",
          "You must not share your account with others or use another person's account.",
          "You are responsible for all activity that occurs under your account.",
          "Notify us immediately if you suspect unauthorised access to your account.",
        ]} />
      </Section>

      <Section t={t} title="6. Acceptable Use">
        <P>You agree not to use the Service to:</P>
        <Ul items={[
          "Post, transmit, or share content that is unlawful, harmful, or harassing",
          "Attempt to bypass or circumvent authentication or security measures",
          "Engage in any automated scraping, crawling, or data mining of the Service",
          "Impersonate any person or entity",
          "Use the Service to promote or facilitate illegal activities",
          "Interfere with the integrity or performance of the Service",
        ]} />
      </Section>

      <Section t={t} title="7. Intellectual Property">
        <P>
          All content, branding, design, and software within the Service is owned by or
          licensed to Sakina and protected by applicable intellectual property laws. You are
          granted a limited, non-exclusive, non-transferable licence to use the Service for
          personal, non-commercial purposes.
        </P>
        <P>
          Content you create within the app (e.g., mood journal notes) remains yours. By
          submitting content, you grant us a limited licence to process it solely to provide
          the Service.
        </P>
      </Section>

      <Section t={t} title="8. AI-Generated Content">
        <P>
          Responses generated by the Sakina AI are produced by a large language model (Google
          Gemini) and may occasionally be inaccurate, incomplete, or inappropriate for your
          situation. You should exercise your own judgement when acting on AI-generated content.
          We are not liable for decisions made based on AI responses.
        </P>
      </Section>

      <Section t={t} title="9. Privacy">
        <P>
          Your use of the Service is subject to our{" "}
          <strong style={{ color: t.gold }}>Privacy Policy</strong>, which is incorporated
          into these Terms by reference. Please read it carefully.
        </P>
      </Section>

      <Section t={t} title="10. Termination">
        <P>
          We reserve the right to suspend or terminate your account at any time for violations
          of these Terms, without prior notice. You may delete your account at any time via
          Settings → Delete Account & Data.
        </P>
        <P>
          Upon termination, your right to use the Service ceases immediately. Sections 4, 7,
          11, and 12 survive termination.
        </P>
      </Section>

      <Section t={t} title="11. Limitation of Liability">
        <P>
          To the maximum extent permitted by applicable law, Sakina and its affiliates shall
          not be liable for any indirect, incidental, special, consequential, or punitive
          damages arising from your use of (or inability to use) the Service.
        </P>
        <P>
          Our total liability for any claim arising from your use of the Service shall not
          exceed the amount you paid us (if any) in the twelve months preceding the claim.
        </P>
      </Section>

      <Section t={t} title="12. Governing Law">
        <P>
          These Terms are governed by the laws of Pakistan, without regard to its conflict-of-law
          provisions. Any disputes shall be resolved in the courts of Lahore, Pakistan, unless
          mandatory local law requires otherwise.
        </P>
      </Section>

      <Section t={t} title="13. Changes to Terms">
        <P>
          We may revise these Terms from time to time. We will notify you of material changes
          via an in-app notice at least 14 days before they take effect. Continued use of the
          Service after the effective date constitutes acceptance of the updated Terms.
        </P>
      </Section>

      <Section t={t} title="14. Contact">
        <P>
          For questions about these Terms, contact us at:{" "}
          <span style={{ color: t.glow }}>legal@sakina.app</span>
        </P>
      </Section>
    </LegalPage>
  );
}
