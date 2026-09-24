import { useState, useEffect, useMemo, useRef } from "react";
import { useAuth } from "./AuthContext";
import { apiFetch } from "./apiKeyHelper";
import { tokens } from "./tokens";

// ─────────────────────────────────────────────
// PROMPTS REPOSITORY (CATEGORIZED)
// ─────────────────────────────────────────────
const PROMPT_CATEGORIES = [
  { id: "all", label: "All Prompts" },
  { id: "reflection", label: "Self-Reflection" },
  { id: "emotional", label: "Emotional Awareness" },
  { id: "gratitude", label: "Gratitude" },
  { id: "growth", label: "Personal Growth" },
  { id: "stress", label: "Stress & Surrender" },
  { id: "thoughts", label: "Thoughts & Feelings" },
  { id: "goals", label: "Goals & Intentions" },
  { id: "daily", label: "Daily Reflection" },
  { id: "spiritual", label: "Spiritual Tranquility" },
];

const CURATED_PROMPTS = [
  // Self-Reflection
  { category: "reflection", text: "What is a gentle lesson that life has been trying to teach you recently?" },
  { category: "reflection", text: "When did you last feel completely at ease with who you are, and what was present in that moment?" },
  { category: "reflection", text: "What part of yourself needs more patience and gentleness today?" },
  { category: "reflection", text: "If you could whisper comforting advice to yourself from one year ago, what would you say?" },

  // Emotional Awareness
  { category: "emotional", text: "What emotion is taking up the most space in your heart today, and what does it need from you?" },
  { category: "emotional", text: "Where in your body are you carrying tension right now, and what is that tension saying?" },
  { category: "emotional", text: "Name one feeling you have been hesitating to acknowledge. Give it permission to be heard." },
  { category: "emotional", text: "How has your mood shifted from morning until this very moment?" },

  // Gratitude
  { category: "gratitude", text: "What is a small, quiet blessing that happened today that you might usually overlook?" },
  { category: "gratitude", text: "Who is someone whose presence brings calm to your life, and why are you grateful for them?" },
  { category: "gratitude", text: "Reflect on a hardship that eventually revealed unexpected goodness or strength within you." },
  { category: "gratitude", text: "Write about three simple comforts in your physical space that you are thankful for." },

  // Personal Growth
  { category: "growth", text: "In what area of your life are you being asked to practice more sabr (patience)?" },
  { category: "growth", text: "What is a habit or belief that served you in the past, but is now ready to be released?" },
  { category: "growth", text: "What does healthy progress look like for you this month without comparing yourself to others?" },
  { category: "growth", text: "What is one fear you are slowly learning to meet with courage?" },

  // Stress & Surrender
  { category: "stress", text: "What is currently within your direct circle of control, and what can you entrust to Allah / the Universe?" },
  { category: "stress", text: "If you were to set down all heavy burdens for just the next ten minutes, what would that feel like?" },
  { category: "stress", text: "Write down everything currently overwhelming your mind, and gently cross out what you cannot solve today." },
  { category: "stress", text: "What does peaceful rest mean for you, and how can you gift yourself that rest tonight?" },

  // Thoughts & Feelings
  { category: "thoughts", text: "Is the thought that has been repeating in your head true, or is it merely anxiety in disguise?" },
  { category: "thoughts", text: "How can you reframe a critical thought today into a compassionate and supportive one?" },
  { category: "thoughts", text: "What story have you been telling yourself about your circumstances, and is there a kinder perspective?" },

  // Goals & Intentions
  { category: "goals", text: "What is one meaningful intention (niyyah) that you want to bring into tomorrow?" },
  { category: "goals", text: "What is one small step you can take toward a goal that feels deeply aligned with your values?" },
  { category: "goals", text: "How do you want people to feel when they interact with you tomorrow?" },

  // Daily Reflection
  { category: "daily", text: "What was the most peaceful moment of your day today?" },
  { category: "daily", text: "What surprised you today, and how did you respond to it?" },
  { category: "daily", text: "If today were a chapter in your book of life, what would you title it?" },

  // Spiritual Tranquility
  { category: "spiritual", text: "Reflect on the verse: 'Unquestionably, by the remembrance of Allah hearts are assured.' (13:28). What brings your heart stillness?" },
  { category: "spiritual", text: "In what moment today did you feel closest to divine peace or mercy?" },
  { category: "spiritual", text: "What prayer or dua is sitting quietly in your heart waiting to be articulated?" },
  { category: "spiritual", text: "How does remembering the vastness of the universe help ease your current worries?" },
];

const MOOD_OPTIONS = [
  "Calm",
  "Grateful",
  "Reflective",
  "Peaceful",
  "Hopeful",
  "Content",
  "Overwhelmed",
  "Anxious",
  "Heavy",
];

const LOCAL_STORAGE_ENTRIES_KEY = "sakina_local_journal_entries";
const LOCAL_STORAGE_DRAFT_KEY = "sakina_journal_draft";

const getInitialDraft = () => {
  try {
    const draft = localStorage.getItem(LOCAL_STORAGE_DRAFT_KEY);
    if (draft) {
      return JSON.parse(draft);
    }
  } catch {
    // Ignore
  }
  return {};
};

export default function JournalTab({ isDark, tokensRef }) {
  const t = tokensRef ? (isDark ? tokensRef.dark : tokensRef.light) : (isDark ? tokens.dark : tokens.light);
  const { user } = useAuth();
  const initialDraft = useRef(getInitialDraft()).current;

  // Mode: 'write' | 'history'
  const [viewMode, setViewMode] = useState("write"); // 'write' or 'history'

  // Zen / Distraction-free mode
  const [isZenMode, setIsZenMode] = useState(false);

  // Prompt state
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [currentPrompt, setCurrentPrompt] = useState(CURATED_PROMPTS[0].text);
  const [promptFade, setPromptFade] = useState(false);

  // Journal form state
  const [editingId, setEditingId] = useState(null);
  const [title, setTitle] = useState(() => initialDraft.title || "");
  const [content, setContent] = useState(() => initialDraft.content || "");
  const [selectedMood, setSelectedMood] = useState(() => initialDraft.mood || "");
  const [attachedPrompt, setAttachedPrompt] = useState(() => initialDraft.prompt || "");
  const [entryDate, setEntryDate] = useState(() => new Date().toISOString().slice(0, 16));

  // Entries list state
  const [entries, setEntries] = useState([]);
  const [loadingEntries, setLoadingEntries] = useState(false);
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState({ text: "", type: "" });

  // Search and filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [filterMood, setFilterMood] = useState("");
  const [sortOrder, setSortOrder] = useState("newest"); // 'newest' | 'oldest'

  // Reader & Delete Modal State
  const [activeReaderEntry, setActiveReaderEntry] = useState(null);
  const [deleteConfirmEntry, setDeleteConfirmEntry] = useState(null);

  // Auto-save draft when writing
  useEffect(() => {
    if (editingId) return; // Don't overwrite draft when editing existing entry
    try {
      if (title.trim() || content.trim()) {
        localStorage.setItem(
          LOCAL_STORAGE_DRAFT_KEY,
          JSON.stringify({
            title,
            content,
            mood: selectedMood,
            prompt: attachedPrompt,
            updatedAt: new Date().toISOString(),
          })
        );
      } else {
        localStorage.removeItem(LOCAL_STORAGE_DRAFT_KEY);
      }
    } catch {
      // Ignore
    }
  }, [title, content, selectedMood, attachedPrompt, editingId]);

  // Fetch entries from backend with fallback to localStorage
  useEffect(() => {
    let isMounted = true;
    setLoadingEntries(true);
    apiFetch("/api/journal")
      .then((res) => {
        if (!res.ok) throw new Error("Backend response error");
        return res.json();
      })
      .then((data) => {
        if (isMounted) {
          const serverEntries = data.entries || [];
          setEntries(serverEntries);
          try {
            localStorage.setItem(LOCAL_STORAGE_ENTRIES_KEY, JSON.stringify(serverEntries));
          } catch {
            // Ignore
          }
        }
      })
      .catch((e) => {
        console.warn("Could not fetch journal entries from API, falling back to local storage:", e);
        if (isMounted) {
          try {
            const local = localStorage.getItem(LOCAL_STORAGE_ENTRIES_KEY);
            if (local) setEntries(JSON.parse(local));
          } catch {
            setEntries([]);
          }
        }
      })
      .finally(() => {
        if (isMounted) setLoadingEntries(false);
      });

    return () => {
      isMounted = false;
    };
  }, [user?.sub]);

  // Generate prompt
  const handleNextPrompt = () => {
    setPromptFade(true);
    setTimeout(() => {
      const filtered = selectedCategory === "all"
        ? CURATED_PROMPTS
        : CURATED_PROMPTS.filter((p) => p.category === selectedCategory);
      const available = filtered.length > 0 ? filtered : CURATED_PROMPTS;
      let nextIndex = Math.floor(Math.random() * available.length);
      // Ensure we don't get the exact same prompt if more than 1 exist
      if (available.length > 1 && available[nextIndex].text === currentPrompt) {
        nextIndex = (nextIndex + 1) % available.length;
      }
      setCurrentPrompt(available[nextIndex].text);
      setPromptFade(false);
    }, 200);
  };

  const handleUsePrompt = (promptText) => {
    const textToUse = promptText || currentPrompt;
    setAttachedPrompt(textToUse);
    if (!title.trim()) {
      setTitle("Reflection on: " + textToUse.slice(0, 32) + "…");
    }
    setViewMode("write");
    showStatus("Prompt applied to journal entry", "info");
  };

  // Helper status notice
  const showStatus = (text, type = "info") => {
    setStatusMessage({ text, type });
    setTimeout(() => setStatusMessage({ text: "", type: "" }), 3500);
  };

  // Save or Update entry
  const handleSaveEntry = async () => {
    if (!title.trim() && !content.trim()) {
      showStatus("Please enter a title or write your thoughts before saving.", "error");
      return;
    }

    setSaving(true);
    const entryData = {
      title: title.trim() || "Untitled Reflection",
      content: content.trim(),
      mood: selectedMood,
      prompt: attachedPrompt,
    };

    let savedEntry = null;

    try {
      if (editingId) {
        // Update existing entry
        const res = await apiFetch(`/api/journal/${editingId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(entryData),
        });
        if (res.ok) {
          savedEntry = await res.json();
        } else {
          throw new Error("Update failed");
        }
      } else {
        // Create new entry
        const res = await apiFetch("/api/journal", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(entryData),
        });
        if (res.ok) {
          savedEntry = await res.json();
        } else {
          throw new Error("Create failed");
        }
      }
    } catch (e) {
      console.warn("Backend save failed, saving locally:", e);
      // Local fallback
      const now = new Date().toISOString();
      if (editingId) {
        savedEntry = {
          id: editingId,
          user_id: user?.sub || "default_user",
          ...entryData,
          updated_at: now,
          created_at: now,
        };
      } else {
        savedEntry = {
          id: Date.now(),
          user_id: user?.sub || "default_user",
          ...entryData,
          created_at: now,
          updated_at: now,
        };
      }
    }

    // Update state list
    setEntries((prev) => {
      let updatedList;
      if (editingId) {
        updatedList = prev.map((e) => (e.id === editingId ? savedEntry : e));
      } else {
        updatedList = [savedEntry, ...prev];
      }
      try {
        localStorage.setItem(LOCAL_STORAGE_ENTRIES_KEY, JSON.stringify(updatedList));
      } catch {
        // Ignore
      }
      return updatedList;
    });

    // Reset editor
    setEditingId(null);
    setTitle("");
    setContent("");
    setSelectedMood("");
    setAttachedPrompt("");
    localStorage.removeItem(LOCAL_STORAGE_DRAFT_KEY);
    setSaving(false);
    showStatus(editingId ? "Reflection updated successfully." : "Reflection saved to your private journal.", "success");
    setViewMode("history");
  };

  // Edit entry
  const handleStartEdit = (entry) => {
    setEditingId(entry.id);
    setTitle(entry.title || "");
    setContent(entry.content || "");
    setSelectedMood(entry.mood || "");
    setAttachedPrompt(entry.prompt || "");
    const safeDate = entry.created_at ? new Date(entry.created_at) : new Date(0);
    setEntryDate(safeDate.toISOString().slice(0, 16));
    setViewMode("write");
    if (activeReaderEntry) setActiveReaderEntry(null);
  };

  // Discard / Reset
  const handleDiscard = () => {
    if (window.confirm("Discard changes to this reflection?")) {
      setEditingId(null);
      setTitle("");
      setContent("");
      setSelectedMood("");
      setAttachedPrompt("");
      localStorage.removeItem(LOCAL_STORAGE_DRAFT_KEY);
      showStatus("Draft cleared.", "info");
    }
  };

  // Delete entry
  const handleDeleteEntry = async (entry) => {
    try {
      await apiFetch(`/api/journal/${entry.id}`, { method: "DELETE" });
    } catch (e) {
      console.warn("Delete request error, clearing locally:", e);
    }

    setEntries((prev) => {
      const filtered = prev.filter((item) => item.id !== entry.id);
      try {
        localStorage.setItem(LOCAL_STORAGE_ENTRIES_KEY, JSON.stringify(filtered));
      } catch {
        // Ignore
      }
      return filtered;
    });

    setDeleteConfirmEntry(null);
    if (activeReaderEntry?.id === entry.id) setActiveReaderEntry(null);
    showStatus("Entry permanently removed.", "info");
  };

  // Export entry as Markdown
  const handleExportEntry = (entry) => {
    const markdown = `# ${entry.title}\n\n**Date:** ${new Date(entry.created_at).toLocaleString()}\n${entry.mood ? `**Mood:** ${entry.mood}\n` : ""}${entry.prompt ? `**Prompt:** ${entry.prompt}\n` : ""}\n---\n\n${entry.content}\n`;
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${entry.title.replace(/[^a-z0-9]/gi, "_").toLowerCase()}_journal.md`;
    link.click();
    URL.revokeObjectURL(url);
    showStatus("Journal entry downloaded as Markdown.", "success");
  };

  // Filtered & sorted entries
  const filteredEntries = useMemo(() => {
    return entries.filter((e) => {
      const matchSearch =
        !searchQuery.trim() ||
        e.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        e.content?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        e.prompt?.toLowerCase().includes(searchQuery.toLowerCase());
      const matchMood = !filterMood || e.mood === filterMood;
      return matchSearch && matchMood;
    }).sort((a, b) => {
      const timeA = new Date(a.created_at).getTime() || 0;
      const timeB = new Date(b.created_at).getTime() || 0;
      return sortOrder === "newest" ? timeB - timeA : timeA - timeB;
    });
  }, [entries, searchQuery, filterMood, sortOrder]);

  // Word count & reading time
  const wordCount = useMemo(() => {
    return content.trim() ? content.trim().split(/\s+/).length : 0;
  }, [content]);

  const readingTime = useMemo(() => {
    return Math.max(1, Math.ceil(wordCount / 200));
  }, [wordCount]);

  return (
    <div
      style={{
        padding: isZenMode ? "2rem" : "2rem 2.4rem",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        gap: "1.5rem",
        overflowY: "auto",
        position: "relative",
      }}
    >
      {/* ─────────────────────────────────────────────
          TOP TOOLBAR / HEADER
          ───────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
          borderBottom: `1px solid ${t.border}`,
          paddingBottom: "1.2rem",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "1.2rem", color: t.gold }}>✎</span>
            <h1 style={{ fontSize: "1.35rem", fontWeight: 400, color: t.textPrimary, letterSpacing: "0.04em" }}>
              Private Journal & Reflections
            </h1>
          </div>
          <p style={{ fontSize: "0.8rem", color: t.textMuted, marginTop: "4px" }}>
            A calm sanctuary to write freely, explore thoughtful prompts, and preserve your personal journey.
          </p>
        </div>

        {/* View Switcher & Zen Mode */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {/* Notification Toast */}
          {statusMessage.text && (
            <div
              style={{
                fontSize: "0.76rem",
                padding: "6px 12px",
                borderRadius: "8px",
                background: statusMessage.type === "error" ? "rgba(239, 68, 68, 0.15)" : `${t.glow}20`,
                border: `1px solid ${statusMessage.type === "error" ? "#ef4444" : t.borderGlow}`,
                color: statusMessage.type === "error" ? "#f87171" : t.glow,
                animation: "fadeIn 0.2s ease",
              }}
            >
              {statusMessage.text}
            </div>
          )}

          {/* Mode toggle */}
          <div
            style={{
              display: "flex",
              background: `${t.bgDeep}90`,
              borderRadius: "12px",
              padding: "4px",
              border: `1px solid ${t.border}`,
            }}
          >
            <button
              onClick={() => setViewMode("write")}
              style={{
                padding: "7px 16px",
                borderRadius: "8px",
                border: "none",
                background: viewMode === "write" ? `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})` : "transparent",
                color: viewMode === "write" ? (isDark ? "#07111C" : "#FFF") : t.textMuted,
                fontSize: "0.8rem",
                fontWeight: 500,
                cursor: "pointer",
                transition: "all 0.2s",
              }}
            >
              ✍️ Write Entry
            </button>
            <button
              onClick={() => setViewMode("history")}
              style={{
                padding: "7px 16px",
                borderRadius: "8px",
                border: "none",
                background: viewMode === "history" ? `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})` : "transparent",
                color: viewMode === "history" ? (isDark ? "#07111C" : "#FFF") : t.textMuted,
                fontSize: "0.8rem",
                fontWeight: 500,
                cursor: "pointer",
                transition: "all 0.2s",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              📖 Past Entries
              <span
                style={{
                  fontSize: "0.68rem",
                  padding: "1px 6px",
                  borderRadius: "10px",
                  background: viewMode === "history" ? "rgba(0,0,0,0.25)" : `${t.glow}20`,
                  color: viewMode === "history" ? "#FFF" : t.gold,
                }}
              >
                {entries.length}
              </span>
            </button>
          </div>

          {/* Zen Mode Button */}
          {viewMode === "write" && (
            <button
              onClick={() => setIsZenMode((z) => !z)}
              style={{
                background: isZenMode ? `${t.glow}25` : "transparent",
                border: `1px solid ${isZenMode ? t.borderGlow : t.border}`,
                borderRadius: "10px",
                padding: "7px 12px",
                color: isZenMode ? t.glow : t.textMuted,
                fontSize: "0.78rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "5px",
              }}
              title="Toggle Zen Mode for distraction-free writing"
            >
              <span>{isZenMode ? "✕ Exit Zen" : "⛶ Zen Mode"}</span>
            </button>
          )}
        </div>
      </div>

      {/* ─────────────────────────────────────────────
          SECTION A & B: WRITING & PROMPT EXPERIENCE
          ───────────────────────────────────────────── */}
      {viewMode === "write" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Reflective Prompt Card (Collapsible in Zen mode) */}
          {!isZenMode && (
            <div
              className="glass-card"
              style={{
                borderRadius: "18px",
                padding: "1.4rem 1.6rem",
                display: "flex",
                flexDirection: "column",
                gap: "12px",
                background: `linear-gradient(135deg, ${t.glassCard}, ${t.bgMid}70)`,
                border: `1px solid ${t.borderGlow}`,
              }}
            >
              {/* Category Filters */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
                <span style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.12em", color: t.gold }}>
                  ✦ Spark Your Reflection
                </span>

                <div style={{ display: "flex", gap: "6px", overflowX: "auto", maxWidth: "100%", paddingBottom: "2px" }}>
                  {PROMPT_CATEGORIES.map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => {
                        setSelectedCategory(cat.id);
                        const filtered = cat.id === "all"
                          ? CURATED_PROMPTS
                          : CURATED_PROMPTS.filter((p) => p.category === cat.id);
                        const chosen = filtered[Math.floor(Math.random() * filtered.length)] || CURATED_PROMPTS[0];
                        setCurrentPrompt(chosen.text);
                      }}
                      style={{
                        background: selectedCategory === cat.id ? `${t.glow}25` : "transparent",
                        border: `1px solid ${selectedCategory === cat.id ? t.borderGlow : t.border}`,
                        borderRadius: "20px",
                        padding: "3px 10px",
                        fontSize: "0.7rem",
                        color: selectedCategory === cat.id ? t.glow : t.textMuted,
                        cursor: "pointer",
                        whiteSpace: "nowrap",
                        transition: "all 0.18s",
                      }}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Prompt Text Display */}
              <div
                style={{
                  fontSize: "1.05rem",
                  fontWeight: 300,
                  fontFamily: "'Cormorant Garamond', Georgia, serif",
                  lineHeight: 1.6,
                  color: t.textPrimary,
                  fontStyle: "italic",
                  opacity: promptFade ? 0 : 1,
                  transition: "opacity 0.2s ease-in-out",
                  minHeight: "48px",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                "{currentPrompt}"
              </div>

              {/* Prompt Actions */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  onClick={handleNextPrompt}
                  style={{
                    background: "transparent",
                    border: `1px solid ${t.border}`,
                    borderRadius: "10px",
                    padding: "6px 14px",
                    color: t.textMuted,
                    fontSize: "0.78rem",
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = t.textPrimary;
                    e.currentTarget.style.borderColor = t.borderGlow;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = t.textMuted;
                    e.currentTarget.style.borderColor = t.border;
                  }}
                >
                  ↻ Another Prompt
                </button>

                <button
                  onClick={() => handleUsePrompt()}
                  style={{
                    background: `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`,
                    border: "none",
                    borderRadius: "10px",
                    padding: "6px 16px",
                    color: isDark ? "#07111C" : "#FFF",
                    fontSize: "0.78rem",
                    fontWeight: 500,
                    cursor: "pointer",
                    boxShadow: `0 2px 10px rgba(196,132,90,0.3)`,
                  }}
                >
                  Write with this Prompt →
                </button>
              </div>
            </div>
          )}

          {/* ─────────────────────────────────────────────
              JOURNAL EDITOR CANVAS
              ───────────────────────────────────────────── */}
          <div
            className="glass-card"
            style={{
              borderRadius: "20px",
              padding: isZenMode ? "2.5rem" : "1.8rem 2rem",
              display: "flex",
              flexDirection: "column",
              gap: "1.2rem",
              background: t.glassCard,
              border: `1px solid ${t.border}`,
            }}
          >
            {/* Editing banner if in edit mode */}
            {editingId && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 14px",
                  borderRadius: "10px",
                  background: `${t.glow}15`,
                  border: `1px solid ${t.borderGlow}`,
                  fontSize: "0.78rem",
                  color: t.glow,
                }}
              >
                <span>Editing existing reflection #{editingId}</span>
                <button
                  onClick={() => {
                    setEditingId(null);
                    setTitle("");
                    setContent("");
                    setSelectedMood("");
                    setAttachedPrompt("");
                  }}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: t.textMuted,
                    fontSize: "0.72rem",
                    cursor: "pointer",
                    textDecoration: "underline",
                  }}
                >
                  Cancel editing & create new
                </button>
              </div>
            )}

            {/* Attached Prompt pill */}
            {attachedPrompt && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 14px",
                  borderRadius: "10px",
                  background: `${t.bgDeep}80`,
                  border: `1px solid ${t.border}`,
                  fontSize: "0.78rem",
                  color: t.textSecond,
                  fontStyle: "italic",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ color: t.gold }}>✦ Prompt:</span>
                  <span>{attachedPrompt}</span>
                </div>
                <button
                  onClick={() => setAttachedPrompt("")}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: t.textMuted,
                    cursor: "pointer",
                    fontSize: "12px",
                  }}
                  title="Remove prompt tag"
                >
                  ✕
                </button>
              </div>
            )}

            {/* Entry Title & Metadata */}
            <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
              <input
                type="text"
                placeholder="Give your reflection a title (or leave blank for Untitled)…"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                style={{
                  flex: 1,
                  minWidth: "260px",
                  background: "transparent",
                  border: "none",
                  borderBottom: `1px solid ${t.border}`,
                  padding: "10px 4px",
                  fontSize: "1.2rem",
                  fontWeight: 400,
                  color: t.textPrimary,
                  outline: "none",
                  letterSpacing: "0.02em",
                }}
              />

              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.78rem", color: t.textMuted }}>
                <span>🕒</span>
                <span>{new Date(entryDate).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
              </div>
            </div>

            {/* Mood Selector Pills */}
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <span style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.1em", color: t.textMuted }}>
                How is your heart feeling? (Optional)
              </span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.55rem" }}>
                {MOOD_OPTIONS.map((mood) => {
                  const isSelected = selectedMood === mood;
                  return (
                    <button
                      key={mood}
                      onClick={() => setSelectedMood(isSelected ? "" : mood)}
                      style={{
                        background: isSelected ? `${t.glow}18` : t.glass,
                        border: `1px solid ${isSelected ? t.borderGlow : t.border}`,
                        borderRadius: "20px",
                        padding: "8px 17px",
                        cursor: "pointer",
                        color: isSelected ? t.glow : t.textSecond,
                        fontSize: "0.8rem",
                        transition: "all 0.2s ease",
                      }}
                      onMouseEnter={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.borderColor = t.borderGlow;
                          e.currentTarget.style.color = t.glow;
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.borderColor = t.border;
                          e.currentTarget.style.color = t.textSecond;
                        }
                      }}
                    >
                      {mood}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Multiline Writing Canvas */}
            <div style={{ position: "relative", minHeight: isZenMode ? "420px" : "280px" }}>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Pour your heart and reflections here. There are no right or wrong words…"
                style={{
                  width: "100%",
                  height: "100%",
                  minHeight: isZenMode ? "420px" : "280px",
                  background: "transparent",
                  border: `1px solid ${t.border}`,
                  borderRadius: "14px",
                  padding: "16px 20px",
                  color: t.textPrimary,
                  fontSize: "0.95rem",
                  fontFamily: "'Inter', sans-serif",
                  lineHeight: 1.8,
                  fontWeight: 300,
                  resize: "vertical",
                  outline: "none",
                  boxShadow: "inset 0 1px 4px rgba(0,0,0,0.15)",
                }}
              />
            </div>

            {/* Footer with stats & Save Button */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                paddingTop: "10px",
                borderTop: `1px solid ${t.border}`,
                flexWrap: "wrap",
                gap: "12px",
              }}
            >
              {/* Stats */}
              <div style={{ display: "flex", gap: "14px", fontSize: "0.75rem", color: t.textMuted }}>
                <span>{wordCount} words</span>
                <span>•</span>
                <span>{content.length} characters</span>
                <span>•</span>
                <span>~{readingTime} min read</span>
                {content && !editingId && (
                  <>
                    <span>•</span>
                    <span style={{ color: t.gold }}>Auto-saved draft</span>
                  </>
                )}
              </div>

              {/* Action Buttons */}
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                {(title || content || editingId) && (
                  <button
                    onClick={handleDiscard}
                    style={{
                      background: "transparent",
                      border: `1px solid ${t.border}`,
                      borderRadius: "10px",
                      padding: "8px 16px",
                      color: t.textMuted,
                      fontSize: "0.8rem",
                      cursor: "pointer",
                      transition: "all 0.2s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "#ef4444")}
                    onMouseLeave={(e) => (e.currentTarget.style.color = t.textMuted)}
                  >
                    Clear Draft
                  </button>
                )}

                <button
                  onClick={handleSaveEntry}
                  disabled={saving || (!title.trim() && !content.trim())}
                  style={{
                    background: title.trim() || content.trim()
                      ? `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`
                      : t.border,
                    border: "none",
                    borderRadius: "10px",
                    padding: "9px 24px",
                    color: isDark ? "#07111C" : "#FFF",
                    fontSize: "0.84rem",
                    fontWeight: 500,
                    cursor: title.trim() || content.trim() ? "pointer" : "default",
                    boxShadow: title.trim() || content.trim() ? `0 4px 16px rgba(196,132,90,0.35)` : "none",
                    transition: "all 0.2s",
                  }}
                >
                  {saving ? "Saving…" : editingId ? "Save Changes" : "Save Reflection"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────
          SECTION C: JOURNAL HISTORY
          ───────────────────────────────────────────── */}
      {viewMode === "history" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.4rem" }}>
          {/* Search, Filter & Sort Controls */}
          <div
            className="glass-card"
            style={{
              padding: "1rem 1.4rem",
              borderRadius: "16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "12px",
              background: t.glassCard,
            }}
          >
            {/* Search Input */}
            <div style={{ flex: 1, minWidth: "220px", position: "relative" }}>
              <input
                type="text"
                placeholder="Search reflections by keywords…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: "100%",
                  background: t.glass,
                  border: `1px solid ${t.border}`,
                  borderRadius: "10px",
                  padding: "8px 12px 8px 32px",
                  color: t.textPrimary,
                  fontSize: "0.82rem",
                  outline: "none",
                }}
              />
              <span style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)", fontSize: "12px", color: t.textMuted }}>
                🔍
              </span>
            </div>

            {/* Mood Filter */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "0.72rem", color: t.textMuted }}>Mood:</span>
              <select
                value={filterMood}
                onChange={(e) => setFilterMood(e.target.value)}
                style={{
                  background: t.glass,
                  border: `1px solid ${t.border}`,
                  borderRadius: "8px",
                  padding: "6px 10px",
                  fontSize: "0.78rem",
                  color: t.textPrimary,
                  outline: "none",
                  cursor: "pointer",
                }}
              >
                <option value="">All Moods</option>
                {MOOD_OPTIONS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            {/* Sort Order */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "0.72rem", color: t.textMuted }}>Order:</span>
              <button
                onClick={() => setSortOrder((o) => (o === "newest" ? "oldest" : "newest"))}
                style={{
                  background: t.glass,
                  border: `1px solid ${t.border}`,
                  borderRadius: "8px",
                  padding: "6px 12px",
                  fontSize: "0.78rem",
                  color: t.textSecond,
                  cursor: "pointer",
                }}
              >
                {sortOrder === "newest" ? "↓ Newest First" : "↑ Oldest First"}
              </button>
            </div>
          </div>

          {/* Entries Grid */}
          {loadingEntries ? (
            <div style={{ padding: "3rem", textAlign: "center", color: t.textMuted, fontSize: "0.88rem" }}>
              Loading your private sanctuary…
            </div>
          ) : filteredEntries.length === 0 ? (
            /* Clean, Calm Empty State */
            <div
              className="glass-card"
              style={{
                padding: "3.5rem 2rem",
                borderRadius: "20px",
                textAlign: "center",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "14px",
                maxWidth: "520px",
                margin: "2rem auto",
              }}
            >
              <div style={{ fontSize: "2.4rem", color: t.gold }}>📖</div>
              <h3 style={{ fontSize: "1.2rem", fontWeight: 400, color: t.textPrimary }}>
                {searchQuery || filterMood ? "No reflections match your search" : "Your Sanctuary Awaits"}
              </h3>
              <p style={{ fontSize: "0.84rem", color: t.textMuted, lineHeight: 1.6, maxWidth: "420px" }}>
                {searchQuery || filterMood
                  ? "Try clearing your mood filter or search terms to see other journal entries."
                  : "You haven't saved any journal entries yet. Whenever you are ready, capture your thoughts, emotions, and gratitude in your private space."}
              </p>
              <button
                onClick={() => {
                  setSearchQuery("");
                  setFilterMood("");
                  setViewMode("write");
                }}
                style={{
                  background: `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`,
                  border: "none",
                  borderRadius: "10px",
                  padding: "10px 24px",
                  color: isDark ? "#07111C" : "#FFF",
                  fontSize: "0.82rem",
                  fontWeight: 500,
                  cursor: "pointer",
                  marginTop: "8px",
                  boxShadow: `0 2px 10px rgba(196,132,90,0.3)`,
                }}
              >
                ✍️ Write First Entry
              </button>
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                gap: "1.2rem",
              }}
            >
              {filteredEntries.map((entry) => {
                const formattedDate = entry.created_at
                  ? new Date(entry.created_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })
                  : "";
                return (
                  <div
                    key={entry.id}
                    className="glass-card"
                    style={{
                      borderRadius: "16px",
                      padding: "1.4rem",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      gap: "12px",
                      background: t.glassCard,
                      border: `1px solid ${t.border}`,
                      cursor: "pointer",
                      transition: "transform 0.2s, border-color 0.2s",
                    }}
                    onClick={() => setActiveReaderEntry(entry)}
                  >
                    <div>
                      {/* Top tags (Date & Mood) */}
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                        <span style={{ fontSize: "0.72rem", color: t.textMuted }}>{formattedDate}</span>
                        {entry.mood && (
                          <span
                            style={{
                              fontSize: "0.7rem",
                              padding: "2px 8px",
                              borderRadius: "12px",
                              background: `${t.glow}20`,
                              border: `1px solid ${t.borderGlow}`,
                              color: t.gold,
                            }}
                          >
                            {entry.mood}
                          </span>
                        )}
                      </div>

                      {/* Title */}
                      <h3
                        style={{
                          fontSize: "1.05rem",
                          fontWeight: 500,
                          color: t.textPrimary,
                          marginBottom: "6px",
                          letterSpacing: "0.02em",
                        }}
                      >
                        {entry.title || "Untitled Reflection"}
                      </h3>

                      {/* Prompt note if present */}
                      {entry.prompt && (
                        <div
                          style={{
                            fontSize: "0.72rem",
                            color: t.textMuted,
                            fontStyle: "italic",
                            marginBottom: "8px",
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                        >
                          ✦ {entry.prompt}
                        </div>
                      )}

                      {/* Excerpt */}
                      <p
                        style={{
                          fontSize: "0.82rem",
                          color: t.textSecond,
                          lineHeight: 1.6,
                          fontWeight: 300,
                          display: "-webkit-box",
                          WebkitLineClamp: 3,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                        }}
                      >
                        {entry.content}
                      </p>
                    </div>

                    {/* Card Actions Footer */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        paddingTop: "8px",
                        borderTop: `1px solid ${t.border}`,
                        marginTop: "4px",
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => setActiveReaderEntry(entry)}
                        style={{
                          background: "transparent",
                          border: "none",
                          color: t.glow,
                          fontSize: "0.75rem",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        Read Full →
                      </button>

                      <div style={{ display: "flex", gap: "8px" }}>
                        {/* Edit */}
                        <button
                          onClick={() => handleStartEdit(entry)}
                          style={{
                            background: "transparent",
                            border: `1px solid ${t.border}`,
                            borderRadius: "6px",
                            padding: "4px 8px",
                            fontSize: "0.72rem",
                            color: t.textMuted,
                            cursor: "pointer",
                          }}
                          title="Edit Reflection"
                        >
                          ✎ Edit
                        </button>

                        {/* Export Markdown */}
                        <button
                          onClick={() => handleExportEntry(entry)}
                          style={{
                            background: "transparent",
                            border: `1px solid ${t.border}`,
                            borderRadius: "6px",
                            padding: "4px 8px",
                            fontSize: "0.72rem",
                            color: t.textMuted,
                            cursor: "pointer",
                          }}
                          title="Download Markdown"
                        >
                          📥
                        </button>

                        {/* Delete */}
                        <button
                          onClick={() => setDeleteConfirmEntry(entry)}
                          style={{
                            background: "transparent",
                            border: `1px solid ${t.border}`,
                            borderRadius: "6px",
                            padding: "4px 8px",
                            fontSize: "0.72rem",
                            color: t.textMuted,
                            cursor: "pointer",
                          }}
                          title="Delete Reflection"
                          onMouseEnter={(e) => (e.currentTarget.style.color = "#ef4444")}
                          onMouseLeave={(e) => (e.currentTarget.style.color = t.textMuted)}
                        >
                          🗑
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────
          READER MODAL (Peaceful, Immersive Reading)
          ───────────────────────────────────────────── */}
      {activeReaderEntry && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 1000,
            background: "rgba(5, 14, 23, 0.75)",
            backdropFilter: "blur(14px)",
            WebkitBackdropFilter: "blur(14px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
            animation: "fadeIn 0.2s ease-out",
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setActiveReaderEntry(null);
          }}
        >
          <div
            className="glass-card"
            style={{
              width: "100%",
              maxWidth: "680px",
              maxHeight: "85vh",
              overflowY: "auto",
              borderRadius: "24px",
              padding: "2.4rem",
              position: "relative",
              border: `1px solid ${t.borderGlow}`,
              boxShadow: "0 25px 70px rgba(0,0,0,0.6)",
              display: "flex",
              flexDirection: "column",
              gap: "1.2rem",
            }}
          >
            {/* Modal Header */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                  <span style={{ fontSize: "0.78rem", color: t.textMuted }}>
                    {new Date(activeReaderEntry.created_at).toLocaleString(undefined, {
                      weekday: "long",
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  {activeReaderEntry.mood && (
                    <span
                      style={{
                        fontSize: "0.74rem",
                        padding: "2px 10px",
                        borderRadius: "12px",
                        background: `${t.glow}20`,
                        border: `1px solid ${t.borderGlow}`,
                        color: t.gold,
                      }}
                    >
                      {activeReaderEntry.mood}
                    </span>
                  )}
                </div>
                <h2 style={{ fontSize: "1.5rem", fontWeight: 400, color: t.textPrimary, letterSpacing: "0.02em" }}>
                  {activeReaderEntry.title || "Untitled Reflection"}
                </h2>
              </div>

              <button
                onClick={() => setActiveReaderEntry(null)}
                style={{
                  background: "transparent",
                  border: `1px solid ${t.border}`,
                  borderRadius: "50%",
                  width: "32px",
                  height: "32px",
                  color: t.textMuted,
                  fontSize: "14px",
                  cursor: "pointer",
                }}
              >
                ✕
              </button>
            </div>

            {/* Prompt Tag */}
            {activeReaderEntry.prompt && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: "12px",
                  background: `${t.bgDeep}80`,
                  border: `1px solid ${t.border}`,
                  fontSize: "0.84rem",
                  color: t.textSecond,
                  fontStyle: "italic",
                }}
              >
                ✦ Prompt: "{activeReaderEntry.prompt}"
              </div>
            )}

            {/* Entry Body */}
            <div
              style={{
                fontSize: "0.98rem",
                color: t.textPrimary,
                lineHeight: 1.85,
                fontWeight: 300,
                whiteSpace: "pre-wrap",
                padding: "8px 0",
              }}
            >
              {activeReaderEntry.content}
            </div>

            {/* Modal Actions */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderTop: `1px solid ${t.border}`,
                paddingTop: "1.2rem",
                marginTop: "0.8rem",
              }}
            >
              <button
                onClick={() => handleExportEntry(activeReaderEntry)}
                style={{
                  background: "transparent",
                  border: `1px solid ${t.border}`,
                  borderRadius: "8px",
                  padding: "6px 14px",
                  fontSize: "0.78rem",
                  color: t.textMuted,
                  cursor: "pointer",
                }}
              >
                📥 Download Markdown
              </button>

              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  onClick={() => handleStartEdit(activeReaderEntry)}
                  style={{
                    background: `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`,
                    border: "none",
                    borderRadius: "8px",
                    padding: "6px 18px",
                    fontSize: "0.78rem",
                    color: isDark ? "#07111C" : "#FFF",
                    fontWeight: 500,
                    cursor: "pointer",
                  }}
                >
                  ✎ Edit Entry
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────
          DELETE CONFIRMATION MODAL
          ───────────────────────────────────────────── */}
      {deleteConfirmEntry && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 1100,
            background: "rgba(5, 14, 23, 0.8)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            className="glass-card"
            style={{
              maxWidth: "420px",
              padding: "2rem",
              borderRadius: "20px",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              gap: "14px",
              border: `1px solid rgba(239, 68, 68, 0.3)`,
            }}
          >
            <div style={{ fontSize: "2rem", color: "#f87171" }}>⚠️</div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 500, color: t.textPrimary }}>
              Permanently delete this reflection?
            </h3>
            <p style={{ fontSize: "0.82rem", color: t.textMuted, lineHeight: 1.6 }}>
              "{deleteConfirmEntry.title || "Untitled Reflection"}" will be completely removed from your local database. This cannot be undone.
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "center", marginTop: "6px" }}>
              <button
                onClick={() => setDeleteConfirmEntry(null)}
                style={{
                  background: t.glass,
                  border: `1px solid ${t.border}`,
                  borderRadius: "10px",
                  padding: "8px 18px",
                  color: t.textPrimary,
                  fontSize: "0.8rem",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteEntry(deleteConfirmEntry)}
                style={{
                  background: "linear-gradient(135deg, #dc2626, #ef4444)",
                  border: "none",
                  borderRadius: "10px",
                  padding: "8px 20px",
                  color: "#FFF",
                  fontSize: "0.8rem",
                  fontWeight: 500,
                  cursor: "pointer",
                  boxShadow: "0 2px 10px rgba(220, 38, 38, 0.4)",
                }}
              >
                Yes, Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
