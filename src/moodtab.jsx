import { useState, useEffect, useRef } from "react";

// ─────────────────────────────────────────────
// MOOD TAB
// Third standalone Sakina module — logs emotional
// states over time and surfaces AI-synthesized
// trend commentary from the /api/mood backend.
//
// Expects the same `tokens` object and `SakinaLogo`
// component already defined in App.jsx. Drop this
// component into App.jsx (or import it) and render
// it as a third nav item alongside ChatTab/DhikrTab.
// ─────────────────────────────────────────────

const MOOD_EMOTIONS = [
    "anxiety", "grief", "panic", "overwhelmed", "loneliness",
    "guilt", "restlessness", "hopelessness", "calm", "gratitude",
    "contentment", "hope",
];

const SIGNAL_COPY = {
    improving: { label: "Trending lighter", icon: "↗" },
    escalating: { label: "Trending heavier", icon: "↘" },
    stable: { label: "Holding steady", icon: "→" },
};

const MoodTab = ({ isDark, tokensRef }) => {
    const t = tokensRef ? (isDark ? tokensRef.dark : tokensRef.light) : (isDark
        ? {
            bgBase: "#07111C", glass: "rgba(13,27,42,0.55)", glassCard: "rgba(18,35,52,0.70)",
            border: "rgba(196,132,90,0.18)", borderGlow: "rgba(196,132,90,0.45)",
            innerLight: "rgba(255,255,255,0.05)", glow: "#C4845A", gold: "#E8B97A",
            goldSoft: "#D4A06A", textPrimary: "#F0E6D3", textSecond: "#9DB4C0",
            textMuted: "#4A6878", shadow: "0 8px 32px rgba(0,0,0,0.45), 0 2px 8px rgba(0,0,0,0.3)",
            shadowGlow: "0 0 40px rgba(196,132,90,0.12), 0 8px 32px rgba(0,0,0,0.45)",
        }
        : {
            bgBase: "#E8DCCB", glass: "rgba(255,253,248,0.62)", glassCard: "rgba(255,253,248,0.82)",
            border: "rgba(160,98,60,0.18)", borderGlow: "rgba(160,98,60,0.42)",
            innerLight: "rgba(255,255,255,0.55)", glow: "#A0622A", gold: "#8A4E1A",
            goldSoft: "#B07040", textPrimary: "#1C2E40", textSecond: "#4A6272",
            textMuted: "#8A9FAA", shadow: "0 8px 32px rgba(100,70,40,0.18), 0 2px 8px rgba(100,70,40,0.10)",
            shadowGlow: "0 0 40px rgba(160,98,60,0.10), 0 8px 32px rgba(100,70,40,0.18)",
        });

    const [mode, setMode] = useState("islamic");
    const [emotion, setEmotion] = useState("");
    const [intensity, setIntensity] = useState(5);
    const [note, setNote] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [dashboard, setDashboard] = useState(null);
    const [dashboardLoading, setDashboardLoading] = useState(true);
    const [justLogged, setJustLogged] = useState(false);

    const labelStyle = {
        fontSize: "0.68rem",
        letterSpacing: "0.14em",
        textTransform: "uppercase",
        color: t.textMuted,
        marginBottom: "1rem",
        display: "block",
    };

    const fetchDashboard = async () => {
        setDashboardLoading(true);
        try {
            const res = await fetch(`/api/mood?mode=${mode}`);
            const data = await res.json();
            setDashboard(data);
        } catch {
            setDashboard({ error: true });
        } finally {
            setDashboardLoading(false);
        }
    };

    useEffect(() => { fetchDashboard(); /* eslint-disable-next-line */ }, [mode]);

    const submitMood = async () => {
        if (!emotion || submitting) return;
        setSubmitting(true);
        try {
            const res = await fetch("/api/mood", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ emotion, intensity, note, mode }),
            });
            const data = await res.json();
            setDashboard(data);
            setJustLogged(true);
            setEmotion("");
            setNote("");
            setIntensity(5);
            setTimeout(() => setJustLogged(false), 2400);
        } catch {
            setDashboard({ error: true });
        } finally {
            setSubmitting(false);
        }
    };

    const trends = dashboard?.trends;
    const signal = trends?.overall_signal ? SIGNAL_COPY[trends.overall_signal] : null;

    return (
        <div style={{ padding: "2.2rem 2rem 2.6rem", overflowY: "auto", height: "100%", animation: "fadeUp 0.5s ease forwards" }}>

            {/* Mode switch */}
            <div style={{ display: "flex", gap: "0.6rem", marginBottom: "2.2rem" }}>
                {[
                    { key: "islamic", label: "Islamic" },
                    { key: "secular", label: "Secular" },
                ].map(opt => (
                    <button
                        key={opt.key}
                        onClick={() => setMode(opt.key)}
                        style={{
                            background: mode === opt.key ? `${t.glow}18` : t.glass,
                            border: `1px solid ${mode === opt.key ? t.borderGlow : t.border}`,
                            borderRadius: "20px",
                            padding: "7px 18px",
                            cursor: "pointer",
                            color: mode === opt.key ? t.glow : t.textMuted,
                            fontSize: "0.76rem",
                            letterSpacing: "0.06em",
                            transition: "all 0.22s ease",
                            backdropFilter: "blur(12px)",
                            WebkitBackdropFilter: "blur(12px)",
                        }}
                    >
                        {opt.label}
                    </button>
                ))}
            </div>

            {/* ── Log entry card ── */}
            <div className="glass-card" style={{ borderRadius: "14px", padding: "1.8rem", marginBottom: "2rem" }}>
                <span style={labelStyle}>How are you feeling right now?</span>

                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.55rem", marginBottom: "1.6rem" }}>
                    {MOOD_EMOTIONS.map(em => (
                        <button
                            key={em}
                            onClick={() => setEmotion(em)}
                            style={{
                                background: emotion === em ? `${t.glow}18` : t.glass,
                                border: `1px solid ${emotion === em ? t.borderGlow : t.border}`,
                                borderRadius: "20px",
                                padding: "8px 17px",
                                cursor: "pointer",
                                color: emotion === em ? t.glow : t.textSecond,
                                fontSize: "0.8rem",
                                transition: "all 0.2s ease",
                                textTransform: "capitalize",
                            }}
                        >
                            {em}
                        </button>
                    ))}
                </div>

                <span style={{ ...labelStyle, marginBottom: "0.6rem" }}>
                    Intensity — {intensity}/10
                </span>
                <input
                    type="range"
                    min={1}
                    max={10}
                    value={intensity}
                    onChange={e => setIntensity(Number(e.target.value))}
                    style={{
                        width: "100%",
                        marginBottom: "1.5rem",
                        accentColor: t.glow,
                        height: "4px",
                    }}
                />

                <span style={{ ...labelStyle, marginBottom: "0.6rem" }}>Anything you'd like to note? (optional)</span>
                <textarea
                    value={note}
                    onChange={e => setNote(e.target.value)}
                    placeholder="A few words about what's going on…"
                    rows={2}
                    style={{
                        width: "100%",
                        background: t.glassCard,
                        backdropFilter: "blur(16px)",
                        WebkitBackdropFilter: "blur(16px)",
                        border: `1px solid ${t.border}`,
                        borderRadius: "10px",
                        padding: "11px 15px",
                        color: t.textPrimary,
                        fontSize: "0.85rem",
                        fontFamily: "'Inter', sans-serif",
                        outline: "none",
                        resize: "none",
                        fontWeight: 300,
                        marginBottom: "1.4rem",
                    }}
                />

                <button
                    onClick={submitMood}
                    disabled={!emotion || submitting}
                    style={{
                        background: emotion && !submitting
                            ? `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`
                            : t.border,
                        border: "none",
                        borderRadius: "10px",
                        padding: "11px 26px",
                        cursor: emotion && !submitting ? "pointer" : "default",
                        color: emotion && !submitting ? (isDark ? t.bgBase : "#fff") : t.textMuted,
                        fontSize: "0.82rem",
                        letterSpacing: "0.04em",
                        boxShadow: emotion && !submitting ? `0 4px 16px rgba(196,132,90,0.3)` : "none",
                        transition: "all 0.22s ease",
                    }}
                >
                    {submitting ? "Logging…" : justLogged ? "✓ Logged" : "Log this feeling"}
                </button>
            </div>

            {/* ── Dashboard ── */}
            {dashboardLoading ? (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "2.5rem 0", gap: "1rem" }}>
                    <div style={{
                        width: "30px", height: "30px", borderRadius: "50%",
                        border: `2px solid ${t.border}`,
                        borderTopColor: t.glow,
                        animation: "spinSlow 1s linear infinite",
                    }} />
                    <span style={{ fontSize: "0.78rem", color: t.textMuted, letterSpacing: "0.08em" }}>Reflecting on your patterns…</span>
                </div>
            ) : dashboard?.error ? (
                <div style={{ color: t.textMuted, fontSize: "0.88rem" }}>Something went wrong loading your history. Please try again.</div>
            ) : trends && !trends.has_data ? (
                <div className="glass-card" style={{ borderRadius: "14px", padding: "1.8rem", textAlign: "center" }}>
                    <p style={{ fontSize: "0.88rem", color: t.textSecond, lineHeight: 1.8, fontWeight: 300 }}>
                        {dashboard.commentary || "Once you start logging how you feel, I'll begin noticing patterns and reflecting them back to you here."}
                    </p>
                </div>
            ) : (
                <>
                    {/* Signal summary row */}
                    {trends && !trends.insufficient_for_trend && (
                        <div style={{ display: "flex", gap: "0.8rem", marginBottom: "1.4rem", flexWrap: "wrap" }}>
                            {signal && (
                                <div className="glass-card" style={{
                                    borderRadius: "12px", padding: "1rem 1.3rem", flex: "1 1 160px",
                                    display: "flex", alignItems: "center", gap: "10px",
                                }}>
                                    <span style={{ fontSize: "1.1rem", color: t.gold }}>{signal.icon}</span>
                                    <div>
                                        <div style={{ fontSize: "0.85rem", color: t.textPrimary, fontWeight: 500 }}>{signal.label}</div>
                                        <div style={{ fontSize: "0.7rem", color: t.textMuted }}>last {trends.window_days} days</div>
                                    </div>
                                </div>
                            )}
                            <div className="glass-card" style={{
                                borderRadius: "12px", padding: "1rem 1.3rem", flex: "1 1 160px",
                            }}>
                                <div style={{ fontSize: "0.85rem", color: t.textPrimary, fontWeight: 500, textTransform: "capitalize" }}>
                                    {trends.dominant_state}
                                </div>
                                <div style={{ fontSize: "0.7rem", color: t.textMuted }}>most frequent state</div>
                            </div>
                            {trends.logging_streak_days > 0 && (
                                <div className="glass-card" style={{
                                    borderRadius: "12px", padding: "1rem 1.3rem", flex: "1 1 160px",
                                }}>
                                    <div style={{ fontSize: "0.85rem", color: t.textPrimary, fontWeight: 500 }}>
                                        {trends.logging_streak_days} day{trends.logging_streak_days === 1 ? "" : "s"}
                                    </div>
                                    <div style={{ fontSize: "0.7rem", color: t.textMuted }}>logging streak</div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* AI commentary */}
                    <div className="glass-card" style={{ borderRadius: "14px", padding: "1.8rem", marginBottom: "1.6rem" }}>
                        <span style={labelStyle}>Reflection</span>
                        <p style={{ fontSize: "0.9rem", lineHeight: 1.85, color: t.textSecond, fontWeight: 300 }}>
                            {dashboard?.commentary}
                        </p>
                    </div>

                    {/* Recent entries */}
                    {dashboard?.recent_entries?.length > 0 && (
                        <div>
                            <span style={labelStyle}>Recent check-ins</span>
                            <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                                {[...dashboard.recent_entries].reverse().map((entry, i) => (
                                    <div key={i} style={{
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "space-between",
                                        background: t.glass,
                                        backdropFilter: "blur(12px)",
                                        WebkitBackdropFilter: "blur(12px)",
                                        border: `1px solid ${t.border}`,
                                        borderRadius: "10px",
                                        padding: "10px 16px",
                                    }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                                            <span style={{ fontSize: "0.82rem", color: t.textPrimary, textTransform: "capitalize" }}>
                                                {entry.state}
                                            </span>
                                            {entry.note && (
                                                <span style={{ fontSize: "0.74rem", color: t.textMuted }}>— {entry.note}</span>
                                            )}
                                        </div>
                                        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
                                            <span style={{ fontSize: "0.72rem", color: t.textMuted }}>
                                                {entry.timestamp?.slice(0, 10)}
                                            </span>
                                            <span style={{
                                                fontSize: "0.7rem",
                                                color: t.gold,
                                                background: `${t.glow}14`,
                                                borderRadius: "10px",
                                                padding: "2px 9px",
                                            }}>
                                                {entry.intensity}/10
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default MoodTab;