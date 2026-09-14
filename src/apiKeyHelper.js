/**
 * BYOK (Bring Your Own Key) and Model Helper for Sakina
 * Manages storing and retrieving user-provided Google Gemini API keys in localStorage
 * and attaching them to API request headers.
 */

const STORAGE_KEY_API_KEY = "sakina_gemini_api_key";
const STORAGE_KEY_MODEL = "sakina_gemini_model";

export const DEFAULT_MODEL = "gemini-2.5-flash";

export const SUPPORTED_MODELS = [
  {
    id: "gemini-2.5-flash",
    name: "Gemini 2.5 Flash (Recommended)",
    description: "Active flagship model — high speed, exceptional emotional synthesis",
    recommended: true,
  },
  {
    id: "gemini-2.5-pro",
    name: "Gemini 2.5 Pro",
    description: "Deep psychological & spiritual reasoning and nuanced reflection",
    recommended: false,
  },
];

export function getStoredApiKey() {
  try {
    return localStorage.getItem(STORAGE_KEY_API_KEY) || "";
  } catch {
    return "";
  }
}

export function setStoredApiKey(key) {
  try {
    if (!key) {
      localStorage.removeItem(STORAGE_KEY_API_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY_API_KEY, key.trim());
    }
  } catch (e) {
    console.error("Failed to save Gemini API key:", e);
  }
}

export function removeStoredApiKey() {
  try {
    localStorage.removeItem(STORAGE_KEY_API_KEY);
  } catch (e) {
    console.error("Failed to remove Gemini API key:", e);
  }
}

export function getStoredModel() {
  try {
    return localStorage.getItem(STORAGE_KEY_MODEL) || DEFAULT_MODEL;
  } catch {
    return DEFAULT_MODEL;
  }
}

export function setStoredModel(modelId) {
  try {
    if (modelId) {
      localStorage.setItem(STORAGE_KEY_MODEL, modelId);
    }
  } catch (e) {
    console.error("Failed to save Gemini Model:", e);
  }
}

/**
 * Enhanced fetch wrapper that automatically attaches the user's
 * Gemini API Key, Gemini Model, and X-User-Id (if available) headers.
 */
export async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  
  const apiKey = getStoredApiKey();
  if (apiKey) {
    headers.set("X-Gemini-API-Key", apiKey);
  }

  const model = getStoredModel();
  if (model) {
    headers.set("X-Gemini-Model", model);
  }

  // Attempt to attach user id if stored in localStorage or session
  try {
    const rawUser = localStorage.getItem("sakina_user");
    if (rawUser) {
      const parsed = JSON.parse(rawUser);
      if (parsed?.sub) {
        headers.set("X-User-Id", parsed.sub);
      }
    }
  } catch {
    // Ignore JSON parse errors
  }

  return fetch(url, {
    ...options,
    headers,
  });
}

/**
 * Verify a Gemini API key against the backend verify endpoint.
 */
export async function verifyApiKey(key, model = DEFAULT_MODEL) {
  if (!key || !key.trim()) {
    return { valid: false, message: "Please provide an API key." };
  }

  try {
    const res = await fetch("/api/key/verify", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Gemini-API-Key": key.trim(),
        "X-Gemini-Model": model,
      },
      body: JSON.stringify({ key: key.trim(), model }),
    });

    const data = await res.json();
    if (res.ok && data.valid) {
      return { valid: true, message: data.message || "Key verified successfully!" };
    }
    return { valid: false, message: data.detail || data.message || "Invalid API key or quota exceeded." };
  } catch {
    return { valid: false, message: "Unable to reach server to verify key." };
  }
}
