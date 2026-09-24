import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { tokens } from "./tokens";

// ─────────────────────────────────────────────
// SPOTIFY URL PARSER & EMBED BUILDER
// ─────────────────────────────────────────────
export function parseSpotifyUrl(input) {
  if (!input || typeof input !== "string") return null;
  const trimmed = input.trim();

  // Handle Spotify URI format: spotify:track:4cOdK2wGLETKBW3PvgPWqT
  const uriMatch = trimmed.match(/^spotify:(track|album|playlist|episode|show):([a-zA-Z0-9]+)/i);
  if (uriMatch) {
    return {
      type: uriMatch[1].toLowerCase(),
      id: uriMatch[2],
      embedUrl: `https://open.spotify.com/embed/${uriMatch[1].toLowerCase()}/${uriMatch[2]}?utm_source=generator&theme=0`,
    };
  }

  // Handle Web URL: https://open.spotify.com/(intl-[a-z]{2}/)?(track|album|playlist|episode|show)/[id]
  const urlPattern = /https?:\/\/open\.spotify\.com\/(?:intl-[a-z]{2}\/)?(track|album|playlist|episode|show)\/([a-zA-Z0-9]+)/i;
  const match = trimmed.match(urlPattern);
  if (match) {
    return {
      type: match[1].toLowerCase(),
      id: match[2],
      embedUrl: `https://open.spotify.com/embed/${match[1].toLowerCase()}/${match[2]}?utm_source=generator&theme=0`,
    };
  }

  return null;
}

// Curated peaceful presets for immediate peaceful ambiance
const SPOTIFY_PRESETS = [
  {
    title: "Surah Ar-Rahman (Mishary Alafasy)",
    subtitle: "Heartfelt Recitation",
    url: "https://open.spotify.com/track/4Pj781V1h4r50w1x2zK36p",
    type: "track",
  },
  {
    title: "Peaceful Rain & Natural Ambience",
    subtitle: "Mindful Soundscape",
    url: "https://open.spotify.com/playlist/37i9dQZF1DX8Uebhn9wzrS",
    type: "playlist",
  },
  {
    title: "Deep Focus & Tranquility",
    subtitle: "Calm Study & Contemplation",
    url: "https://open.spotify.com/playlist/37i9dQZF1DWZeKCadgRdKQ",
    type: "playlist",
  },
  {
    title: "Spiritual Solitude & Gentle Oud",
    subtitle: "Contemplative Acoustics",
    url: "https://open.spotify.com/playlist/37i9dQZF1DX3O4uV0kGj9G",
    type: "playlist",
  },
];

const LOCAL_STORAGE_SPOTIFY_KEY = "sakina_spotify_embed_url";
const LOCAL_STORAGE_VOLUME_KEY = "sakina_audio_volume";

export default function AudioPlayer({ isDark, tokensRef }) {
  const t = tokensRef ? (isDark ? tokensRef.dark : tokensRef.light) : (isDark ? tokens.dark : tokens.light);

  // Soundscape expansion modal
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState("local"); // 'local' | 'spotify'

  // Spotify state
  const [spotifyInput, setSpotifyInput] = useState("");
  const [spotifyEmbedUrl, setSpotifyEmbedUrl] = useState(() => {
    try {
      return localStorage.getItem(LOCAL_STORAGE_SPOTIFY_KEY) || "";
    } catch {
      return "";
    }
  });
  const [spotifyLoading, setSpotifyLoading] = useState(false);
  const [spotifyError, setSpotifyError] = useState("");
  const [spotifyType, setSpotifyType] = useState("playlist");

  // Local audio state
  const [audioFile, setAudioFile] = useState(null);
  const [audioSrc, setAudioSrc] = useState(null);
  const [fileName, setFileName] = useState("");
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_VOLUME_KEY);
      return saved !== null ? parseFloat(saved) : 0.8;
    } catch {
      return 0.8;
    }
  });
  const [isMuted, setIsMuted] = useState(false);
  const [isLooping, setIsLooping] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [audioError, setAudioError] = useState("");
  const [activeSource, setActiveSource] = useState(null); // 'local' | 'spotify' | null

  const audioRef = useRef(null);
  const fileInputRef = useRef(null);

  // Initialize or update volume
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? 0 : volume;
      audioRef.current.playbackRate = playbackRate;
      audioRef.current.loop = isLooping;
    }
    try {
      localStorage.setItem(LOCAL_STORAGE_VOLUME_KEY, volume.toString());
    } catch {
      // Ignore
    }
  }, [volume, isMuted, playbackRate, isLooping]);

  // Clean up object URL on unmount or file change
  useEffect(() => {
    return () => {
      if (audioSrc) {
        URL.revokeObjectURL(audioSrc);
      }
    };
  }, [audioSrc]);

  // Handle local file selection
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Check supported types
    const validTypes = ["audio/mp3", "audio/mpeg", "audio/wav", "audio/wave", "audio/x-wav", "audio/ogg", "audio/aac", "audio/m4a", "audio/x-m4a", "audio/flac"];
    const extension = file.name.split(".").pop()?.toLowerCase();
    const validExtensions = ["mp3", "wav", "ogg", "m4a", "aac", "flac"];

    if (!validTypes.includes(file.type) && !validExtensions.includes(extension)) {
      setAudioError("Unsupported format. Please select an MP3, WAV, OGG, M4A, AAC, or FLAC audio file.");
      return;
    }

    setAudioError("");
    if (audioSrc) {
      URL.revokeObjectURL(audioSrc);
    }

    const objectUrl = URL.createObjectURL(file);
    setAudioFile(file);
    setFileName(file.name);
    setAudioSrc(objectUrl);
    setCurrentTime(0);
    setDuration(0);

    // Pause any Spotify playing note
    setActiveSource("local");

    // Auto-play the chosen file
    setTimeout(() => {
      if (audioRef.current) {
        audioRef.current.play().then(() => {
          setIsPlaying(true);
        }).catch((err) => {
          console.warn("Autoplay was blocked or audio failed:", err);
          setIsPlaying(false);
        });
      }
    }, 150);
  };

  // Local audio playback toggles
  const togglePlay = () => {
    if (!audioRef.current || !audioSrc) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().then(() => {
        setIsPlaying(true);
        setActiveSource("local");
      }).catch((err) => {
        setAudioError("Unable to play audio. The file might be corrupted or format unsupported.");
        setIsPlaying(false);
      });
    }
  };

  const seekRelative = (seconds) => {
    if (!audioRef.current) return;
    const newTime = Math.max(0, Math.min(duration, audioRef.current.currentTime + seconds));
    audioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const handleSeek = (e) => {
    const seekTime = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = seekTime;
    }
    setCurrentTime(seekTime);
  };

  const handleVolumeChange = (e) => {
    const val = parseFloat(e.target.value);
    setVolume(val);
    if (isMuted && val > 0) setIsMuted(false);
  };

  const toggleMute = () => {
    setIsMuted((prev) => !prev);
  };

  const clearLocalAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
    if (audioSrc) {
      URL.revokeObjectURL(audioSrc);
    }
    setAudioFile(null);
    setAudioSrc(null);
    setFileName("");
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    setAudioError("");
    if (activeSource === "local") setActiveSource(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Spotify handlers
  const handleEmbedSpotify = (urlToUse) => {
    const targetUrl = urlToUse || spotifyInput;
    if (!targetUrl.trim()) {
      setSpotifyError("Please paste a Spotify URL or URI.");
      return;
    }

    const parsed = parseSpotifyUrl(targetUrl);
    if (!parsed) {
      setSpotifyError("Invalid Spotify link. Please paste a track, album, playlist, episode, or show URL.");
      return;
    }

    setSpotifyError("");
    setSpotifyLoading(true);
    setSpotifyEmbedUrl(parsed.embedUrl);
    setSpotifyType(parsed.type);
    setActiveSource("spotify");

    // Pause local audio when spotify is embedded and activated
    if (audioRef.current && isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    }

    try {
      localStorage.setItem(LOCAL_STORAGE_SPOTIFY_KEY, parsed.embedUrl);
    } catch {
      // Ignore
    }

    // Reset loading state after a brief visual buffer
    setTimeout(() => {
      setSpotifyLoading(false);
    }, 1200);
  };

  const handleClearSpotify = () => {
    setSpotifyEmbedUrl("");
    setSpotifyInput("");
    setSpotifyError("");
    if (activeSource === "spotify") setActiveSource(null);
    try {
      localStorage.removeItem(LOCAL_STORAGE_SPOTIFY_KEY);
    } catch {
      // Ignore
    }
  };

  // Helper format time MM:SS
  const formatTime = (secs) => {
    if (!secs || isNaN(secs)) return "00:00";
    const minutes = Math.floor(secs / 60);
    const seconds = Math.floor(secs % 60);
    return `${minutes < 10 ? "0" : ""}${minutes}:${seconds < 10 ? "0" : ""}${seconds}`;
  };

  const isEmbedPlaylistOrAlbum = spotifyType === "playlist" || spotifyType === "album" || spotifyType === "show";

  return (
    <>
      {/* Hidden native audio element */}
      <audio
        ref={audioRef}
        src={audioSrc || undefined}
        onTimeUpdate={() => {
          if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
        }}
        onLoadedMetadata={() => {
          if (audioRef.current) setDuration(audioRef.current.duration || 0);
        }}
        onEnded={() => {
          if (!isLooping) {
            setIsPlaying(false);
            setCurrentTime(0);
          }
        }}
        onError={() => {
          setAudioError("Playback error: unable to decode audio file.");
          setIsPlaying(false);
        }}
      />

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*,.mp3,.wav,.ogg,.m4a,.aac,.flac"
        onChange={handleFileChange}
        style={{ display: "none" }}
      />

      {/* ─────────────────────────────────────────────
          TOP HEADER INTEGRATED SOUNDSCAPE CONTROL
          ───────────────────────────────────────────── */}
      <div
        style={{
          position: "relative",
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "5px 14px",
          background: t.glassCard,
          backdropFilter: "blur(20px) saturate(1.5)",
          WebkitBackdropFilter: "blur(20px) saturate(1.5)",
          border: `1px solid ${activeSource ? t.borderGlow : t.border}`,
          borderRadius: "50px",
          boxShadow: activeSource ? t.shadowGlow : t.shadow,
          transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
          marginLeft: "auto",
        }}
      >
        {/* Source Status & Play Icon */}
        <div
          onClick={() => setIsExpanded(true)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "9px",
            cursor: "pointer",
          }}
          title="Click to open Soundscape Controls"
        >
          <div
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "50%",
              background: `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "13px",
              color: isDark ? "#07111C" : "#FFFFFF",
              boxShadow: isPlaying ? `0 0 12px ${t.glow}` : "none",
              animation: isPlaying ? "pulse 2s infinite" : "none",
            }}
          >
            {activeSource === "spotify" ? "♫" : isPlaying ? "▶" : "♪"}
          </div>

          <div style={{ display: "flex", flexDirection: "column", maxWidth: "160px" }}>
            <span
              style={{
                fontSize: "0.78rem",
                fontWeight: 500,
                color: t.textPrimary,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                letterSpacing: "0.02em",
              }}
            >
              {audioSrc
                ? fileName || "Local Audio"
                : spotifyEmbedUrl
                ? "Spotify Soundscape"
                : "Soundscape & Music"}
            </span>
            <span
              style={{
                fontSize: "0.66rem",
                color: activeSource ? t.gold : t.textMuted,
                display: "flex",
                alignItems: "center",
                gap: "5px",
              }}
            >
              {activeSource === "local" ? (
                <>
                  <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", background: "#4ade80" }} />
                  {isPlaying ? "Playing Local" : "Local Audio Paused"}
                </>
              ) : activeSource === "spotify" ? (
                <>
                  <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", background: "#1DB954" }} />
                  Spotify Active
                </>
              ) : (
                "Ambient audio offline"
              )}
            </span>
          </div>
        </div>

        {/* Quick controls if local audio loaded */}
        {audioSrc && (
          <div style={{ display: "flex", alignItems: "center", gap: "6px", borderLeft: `1px solid ${t.border}`, paddingLeft: "10px" }}>
            <button
              onClick={togglePlay}
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: t.glow,
                fontSize: "14px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                transition: "background 0.2s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = `${t.glow}20`)}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              title={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? "❚❚" : "▶"}
            </button>
            <span style={{ fontSize: "0.7rem", color: t.textMuted, minWidth: "35px" }}>
              {formatTime(currentTime)}
            </span>
          </div>
        )}

        {/* Expand / Soundscape Panel Button */}
        <button
          onClick={() => setIsExpanded(true)}
          style={{
            background: `${t.glow}18`,
            border: `1px solid ${t.border}`,
            borderRadius: "20px",
            padding: "4px 10px",
            color: t.glow,
            fontSize: "0.72rem",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "5px",
            transition: "all 0.2s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = `${t.glow}30`;
            e.currentTarget.style.borderColor = t.borderGlow;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = `${t.glow}18`;
            e.currentTarget.style.borderColor = t.border;
          }}
        >
          <span>✦ Soundscape</span>
        </button>
      </div>

      {/* ─────────────────────────────────────────────
          EXPANDED SOUNDSCAPE MODAL / PANEL
          ───────────────────────────────────────────── */}
      {isExpanded && typeof document !== "undefined" && createPortal(
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 99999,
            background: "rgba(5, 14, 23, 0.75)",
            backdropFilter: "blur(14px)",
            WebkitBackdropFilter: "blur(14px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
            animation: "fadeIn 0.25s ease-out",
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsExpanded(false);
          }}
        >
          <div
            className="glass-card"
            style={{
              width: "100%",
              maxWidth: "680px",
              maxHeight: "90vh",
              overflowY: "auto",
              borderRadius: "24px",
              padding: "2rem",
              position: "relative",
              border: `1px solid ${t.borderGlow}`,
              boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
              display: "flex",
              flexDirection: "column",
              gap: "1.4rem",
            }}
          >
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "1.4rem", color: t.gold }}>✦</span>
                <div>
                  <h2 style={{ fontSize: "1.2rem", fontWeight: 400, color: t.textPrimary, letterSpacing: "0.04em" }}>
                    Soundscape & Audio Sanctuary
                  </h2>
                  <p style={{ fontSize: "0.78rem", color: t.textMuted, marginTop: "2px" }}>
                    Listen to soothing Quran recitations, local audio reflections, or Spotify playlists.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsExpanded(false)}
                style={{
                  background: "transparent",
                  border: `1px solid ${t.border}`,
                  borderRadius: "50%",
                  width: "32px",
                  height: "32px",
                  color: t.textMuted,
                  fontSize: "14px",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
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
                ✕
              </button>
            </div>

            {/* Navigation Tabs (Local Audio vs Spotify) */}
            <div
              style={{
                display: "flex",
                gap: "8px",
                padding: "4px",
                background: `${t.bgDeep}80`,
                borderRadius: "14px",
                border: `1px solid ${t.border}`,
              }}
            >
              <button
                onClick={() => setActiveTab("local")}
                style={{
                  flex: 1,
                  padding: "9px 16px",
                  borderRadius: "10px",
                  border: "none",
                  background: activeTab === "local" ? `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})` : "transparent",
                  color: activeTab === "local" ? (isDark ? "#07111C" : "#FFF") : t.textMuted,
                  fontWeight: activeTab === "local" ? 500 : 400,
                  fontSize: "0.82rem",
                  cursor: "pointer",
                  transition: "all 0.2s",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "7px",
                }}
              >
                <span>📁</span> Local Audio File
                {audioSrc && <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: isPlaying ? "#4ade80" : t.gold }} />}
              </button>
              <button
                onClick={() => setActiveTab("spotify")}
                style={{
                  flex: 1,
                  padding: "9px 16px",
                  borderRadius: "10px",
                  border: "none",
                  background: activeTab === "spotify" ? `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})` : "transparent",
                  color: activeTab === "spotify" ? (isDark ? "#07111C" : "#FFF") : t.textMuted,
                  fontWeight: activeTab === "spotify" ? 500 : 400,
                  fontSize: "0.82rem",
                  cursor: "pointer",
                  transition: "all 0.2s",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "7px",
                }}
              >
                <span>♫</span> Spotify Embed Player
                {spotifyEmbedUrl && <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#1DB954" }} />}
              </button>
            </div>

            {/* Active Source Notice */}
            {activeSource && (
              <div
                style={{
                  padding: "8px 14px",
                  borderRadius: "10px",
                  background: activeSource === "local" ? `${t.glow}15` : "rgba(29, 185, 84, 0.12)",
                  border: `1px solid ${activeSource === "local" ? t.borderGlow : "rgba(29, 185, 84, 0.3)"}`,
                  fontSize: "0.75rem",
                  color: activeSource === "local" ? t.gold : "#1DB954",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span>
                  ● Active Audio Stream: <strong>{activeSource === "local" ? "Local Audio Player" : "Spotify Embed"}</strong>
                </span>
                <span style={{ fontSize: "0.7rem", color: t.textMuted }}>
                  {activeSource === "local" ? "Playing offline from PC" : "Streaming via Spotify Iframe"}
                </span>
              </div>
            )}

            {/* ─────────────────────────────────────────────
                TAB 1: LOCAL AUDIO FILE PLAYER
                ───────────────────────────────────────────── */}
            {activeTab === "local" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.2rem" }}>
                {/* Upload / Select Button Card */}
                <div
                  style={{
                    border: `1px dashed ${t.borderGlow}`,
                    borderRadius: "16px",
                    padding: audioSrc ? "1.2rem 1.4rem" : "2rem",
                    textAlign: "center",
                    background: `${t.glass}30`,
                    transition: "all 0.25s",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "10px",
                  }}
                >
                  <div
                    style={{
                      width: "44px",
                      height: "44px",
                      borderRadius: "50%",
                      background: `${t.glow}20`,
                      color: t.glow,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "20px",
                    }}
                  >
                    📂
                  </div>

                  <div>
                    <h3 style={{ fontSize: "0.95rem", fontWeight: 500, color: t.textPrimary }}>
                      {audioSrc ? fileName : "Upload Audio from your PC"}
                    </h3>
                    <p style={{ fontSize: "0.76rem", color: t.textMuted, marginTop: "4px" }}>
                      Plays privately on your device. Supports MP3, WAV, OGG, M4A, AAC, and FLAC.
                    </p>
                  </div>

                  <div style={{ display: "flex", gap: "10px", marginTop: "4px" }}>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      style={{
                        background: `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`,
                        border: "none",
                        borderRadius: "10px",
                        padding: "8px 18px",
                        color: isDark ? "#07111C" : "#FFF",
                        fontSize: "0.8rem",
                        fontWeight: 500,
                        cursor: "pointer",
                        boxShadow: `0 2px 10px rgba(196,132,90,0.3)`,
                      }}
                    >
                      {audioSrc ? "Choose Another File" : "Choose Audio File"}
                    </button>

                    {audioSrc && (
                      <button
                        onClick={clearLocalAudio}
                        style={{
                          background: "transparent",
                          border: `1px solid ${t.border}`,
                          borderRadius: "10px",
                          padding: "8px 16px",
                          color: t.textMuted,
                          fontSize: "0.8rem",
                          cursor: "pointer",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = "#ef4444")}
                        onMouseLeave={(e) => (e.currentTarget.style.color = t.textMuted)}
                      >
                        Remove Audio
                      </button>
                    )}
                  </div>
                </div>

                {/* Error message */}
                {audioError && (
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: "10px",
                      background: "rgba(239, 68, 68, 0.12)",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      color: "#f87171",
                      fontSize: "0.78rem",
                    }}
                  >
                    ⚠️ {audioError}
                  </div>
                )}

                {/* Player Controls (When an audio file is loaded) */}
                {audioSrc && (
                  <div
                    className="glass-card"
                    style={{
                      padding: "1.4rem",
                      borderRadius: "18px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "1.1rem",
                      background: t.glassCard,
                    }}
                  >
                    {/* Scrub Progress Bar */}
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      <input
                        type="range"
                        min={0}
                        max={duration || 100}
                        step={0.1}
                        value={currentTime}
                        onChange={handleSeek}
                        style={{
                          width: "100%",
                          cursor: "pointer",
                          accentColor: t.glow,
                        }}
                      />
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.72rem", color: t.textMuted }}>
                        <span>{formatTime(currentTime)}</span>
                        <span>{formatTime(duration)}</span>
                      </div>
                    </div>

                    {/* Main playback buttons */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "16px" }}>
                      {/* Seek -10s */}
                      <button
                        onClick={() => seekRelative(-10)}
                        style={{
                          background: "transparent",
                          border: `1px solid ${t.border}`,
                          borderRadius: "50%",
                          width: "36px",
                          height: "36px",
                          color: t.textPrimary,
                          fontSize: "0.74rem",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                        title="Seek backward 10s"
                      >
                        -10s
                      </button>

                      {/* Play/Pause */}
                      <button
                        onClick={togglePlay}
                        style={{
                          background: `linear-gradient(135deg, ${t.glow}, ${t.goldSoft})`,
                          border: "none",
                          borderRadius: "50%",
                          width: "52px",
                          height: "52px",
                          color: isDark ? "#07111C" : "#FFF",
                          fontSize: "18px",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          boxShadow: `0 4px 18px rgba(196,132,90,0.4)`,
                          transition: "transform 0.15s ease",
                        }}
                        onMouseDown={(e) => (e.currentTarget.style.transform = "scale(0.95)")}
                        onMouseUp={(e) => (e.currentTarget.style.transform = "scale(1)")}
                        title={isPlaying ? "Pause" : "Play"}
                      >
                        {isPlaying ? "❚❚" : "▶"}
                      </button>

                      {/* Seek +10s */}
                      <button
                        onClick={() => seekRelative(10)}
                        style={{
                          background: "transparent",
                          border: `1px solid ${t.border}`,
                          borderRadius: "50%",
                          width: "36px",
                          height: "36px",
                          color: t.textPrimary,
                          fontSize: "0.74rem",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                        title="Seek forward 10s"
                      >
                        +10s
                      </button>
                    </div>

                    {/* Secondary Controls: Volume, Mute, Loop, Speed */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        paddingTop: "8px",
                        borderTop: `1px solid ${t.border}`,
                        flexWrap: "wrap",
                        gap: "12px",
                      }}
                    >
                      {/* Volume Slider & Mute */}
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <button
                          onClick={toggleMute}
                          style={{
                            background: "transparent",
                            border: "none",
                            cursor: "pointer",
                            fontSize: "14px",
                            color: isMuted ? t.textMuted : t.gold,
                          }}
                          title={isMuted ? "Unmute" : "Mute"}
                        >
                          {isMuted || volume === 0 ? "🔇" : volume < 0.5 ? "🔉" : "🔊"}
                        </button>
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.01}
                          value={isMuted ? 0 : volume}
                          onChange={handleVolumeChange}
                          style={{ width: "80px", cursor: "pointer", accentColor: t.glow }}
                        />
                        <span style={{ fontSize: "0.7rem", color: t.textMuted, width: "28px" }}>
                          {Math.round((isMuted ? 0 : volume) * 100)}%
                        </span>
                      </div>

                      {/* Loop & Speed */}
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        {/* Loop Toggle */}
                        <button
                          onClick={() => setIsLooping((l) => !l)}
                          style={{
                            background: isLooping ? `${t.glow}25` : "transparent",
                            border: `1px solid ${isLooping ? t.borderGlow : t.border}`,
                            borderRadius: "8px",
                            padding: "4px 9px",
                            fontSize: "0.72rem",
                            color: isLooping ? t.glow : t.textMuted,
                            cursor: "pointer",
                          }}
                          title="Repeat Audio"
                        >
                          🔁 Repeat {isLooping ? "On" : "Off"}
                        </button>

                        {/* Playback speed selector */}
                        <select
                          value={playbackRate}
                          onChange={(e) => setPlaybackRate(parseFloat(e.target.value))}
                          style={{
                            background: t.glass,
                            border: `1px solid ${t.border}`,
                            borderRadius: "8px",
                            padding: "4px 8px",
                            fontSize: "0.72rem",
                            color: t.textPrimary,
                            outline: "none",
                            cursor: "pointer",
                          }}
                        >
                          <option value={0.75}>0.75x</option>
                          <option value={1.0}>1.0x (Normal)</option>
                          <option value={1.25}>1.25x</option>
                          <option value={1.5}>1.5x</option>
                        </select>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ─────────────────────────────────────────────
                TAB 2: SPOTIFY EMBED PLAYER
                ───────────────────────────────────────────── */}
            {activeTab === "spotify" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.2rem" }}>
                {/* Spotify URL Input Section */}
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  <label style={{ fontSize: "0.74rem", textTransform: "uppercase", letterSpacing: "0.1em", color: t.textMuted }}>
                    Spotify URL or URI
                  </label>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <input
                      type="text"
                      placeholder="Paste Spotify track, album, or playlist link…"
                      value={spotifyInput}
                      onChange={(e) => setSpotifyInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleEmbedSpotify();
                      }}
                      style={{
                        flex: 1,
                        background: t.glassCard,
                        border: `1px solid ${t.border}`,
                        borderRadius: "12px",
                        padding: "10px 14px",
                        color: t.textPrimary,
                        fontSize: "0.84rem",
                        fontFamily: "'Inter', sans-serif",
                        outline: "none",
                      }}
                    />
                    <button
                      onClick={() => handleEmbedSpotify()}
                      style={{
                        background: `linear-gradient(135deg, #1DB954, #1ed760)`,
                        border: "none",
                        borderRadius: "12px",
                        padding: "0 18px",
                        color: "#07111C",
                        fontWeight: 600,
                        fontSize: "0.82rem",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        boxShadow: "0 2px 10px rgba(29, 185, 84, 0.3)",
                      }}
                    >
                      Embed
                    </button>
                  </div>
                </div>

                {/* Error message */}
                {spotifyError && (
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: "10px",
                      background: "rgba(239, 68, 68, 0.12)",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      color: "#f87171",
                      fontSize: "0.78rem",
                    }}
                  >
                    ⚠️ {spotifyError}
                  </div>
                )}

                {/* Quick Presets for Instant Spiritual & Calm Playback */}
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  <span style={{ fontSize: "0.72rem", color: t.textMuted, letterSpacing: "0.06em" }}>
                    Or try a peaceful curated preset:
                  </span>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                    {SPOTIFY_PRESETS.map((preset, idx) => (
                      <div
                        key={idx}
                        onClick={() => {
                          setSpotifyInput(preset.url);
                          handleEmbedSpotify(preset.url);
                        }}
                        style={{
                          padding: "8px 12px",
                          borderRadius: "10px",
                          background: `${t.glass}40`,
                          border: `1px solid ${t.border}`,
                          cursor: "pointer",
                          transition: "all 0.2s",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = "#1DB954";
                          e.currentTarget.style.background = `${t.glow}10`;
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = t.border;
                          e.currentTarget.style.background = `${t.glass}40`;
                        }}
                      >
                        <div style={{ fontSize: "0.78rem", fontWeight: 500, color: t.textPrimary, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {preset.title}
                        </div>
                        <div style={{ fontSize: "0.68rem", color: t.textMuted }}>{preset.subtitle}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Spotify Embedded Player Container */}
                {spotifyEmbedUrl && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "6px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "0.72rem", color: "#1DB954", display: "flex", alignItems: "center", gap: "5px" }}>
                        <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#1DB954" }} />
                        Official Spotify Embed Loaded
                      </span>
                      <button
                        onClick={handleClearSpotify}
                        style={{
                          background: "transparent",
                          border: "none",
                          fontSize: "0.72rem",
                          color: t.textMuted,
                          cursor: "pointer",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = "#ef4444")}
                        onMouseLeave={(e) => (e.currentTarget.style.color = t.textMuted)}
                      >
                        Remove Embed
                      </button>
                    </div>

                    {spotifyLoading && (
                      <div
                        style={{
                          height: isEmbedPlaylistOrAlbum ? "352px" : "152px",
                          borderRadius: "12px",
                          background: `${t.bgDeep}90`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: t.textMuted,
                          fontSize: "0.82rem",
                          border: `1px solid ${t.border}`,
                        }}
                      >
                        Loading Spotify Player…
                      </div>
                    )}

                    <iframe
                      src={spotifyEmbedUrl}
                      width="100%"
                      height={isEmbedPlaylistOrAlbum ? "352" : "152"}
                      frameBorder="0"
                      allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
                      loading="lazy"
                      style={{
                        borderRadius: "14px",
                        border: `1px solid ${t.border}`,
                        boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
                        display: spotifyLoading ? "none" : "block",
                      }}
                      onLoad={() => setSpotifyLoading(false)}
                      onError={() => {
                        setSpotifyLoading(false);
                        setSpotifyError("Unable to load Spotify Embed. Please check the URL or your network connection.");
                      }}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
