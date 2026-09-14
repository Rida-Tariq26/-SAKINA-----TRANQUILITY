/**
 * tokens.js — shared design tokens for Sakina.
 *
 * Extracted from App.jsx so that standalone component files
 * (CookieBanner, GoogleSignIn, SettingsTab, etc.) can import
 * them without creating a circular dependency on the monolithic App.
 *
 * App.jsx still defines its own `tokens` object internally for
 * backward-compatibility; keep them in sync when updating colours.
 */
export const tokens = {
  dark: {
    bgBase:      "#07111C",
    bgMid:       "#0D1B2A",
    bgDeep:      "#050E17",
    glass:       "rgba(13,27,42,0.55)",
    glassBright: "rgba(25,45,65,0.60)",
    glassCard:   "rgba(18,35,52,0.70)",
    border:      "rgba(196,132,90,0.18)",
    borderGlow:  "rgba(196,132,90,0.45)",
    innerLight:  "rgba(255,255,255,0.05)",
    glow:        "#C4845A",
    gold:        "#E8B97A",
    goldSoft:    "#D4A06A",
    textPrimary: "#F0E6D3",
    textSecond:  "#9DB4C0",
    textMuted:   "#4A6878",
    userBubble:  "rgba(30,58,82,0.75)",
    aiBubble:    "rgba(13,27,42,0.80)",
    shadow:      "0 8px 32px rgba(0,0,0,0.45), 0 2px 8px rgba(0,0,0,0.3)",
    shadowGlow:  "0 0 40px rgba(196,132,90,0.12), 0 8px 32px rgba(0,0,0,0.45)",
  },
  light: {
    bgBase:      "#E8DCCB",
    bgMid:       "#F0E6D4",
    bgDeep:      "#DDD0BB",
    glass:       "rgba(255,253,248,0.62)",
    glassBright: "rgba(255,253,248,0.78)",
    glassCard:   "rgba(255,253,248,0.82)",
    border:      "rgba(160,98,60,0.18)",
    borderGlow:  "rgba(160,98,60,0.42)",
    innerLight:  "rgba(255,255,255,0.55)",
    glow:        "#A0622A",
    gold:        "#8A4E1A",
    goldSoft:    "#B07040",
    textPrimary: "#1C2E40",
    textSecond:  "#4A6272",
    textMuted:   "#8A9FAA",
    userBubble:  "rgba(220,200,175,0.80)",
    aiBubble:    "rgba(255,253,248,0.88)",
    shadow:      "0 8px 32px rgba(100,70,40,0.18), 0 2px 8px rgba(100,70,40,0.10)",
    shadowGlow:  "0 0 40px rgba(160,98,60,0.10), 0 8px 32px rgba(100,70,40,0.18)",
  },
};
