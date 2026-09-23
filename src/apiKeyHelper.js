/**
 * BYOK (Bring Your Own Key) and Model Helper for Sakina
 * Manages storing and retrieving user-provided Google Gemini API keys in localStorage
 * and attaching them to API request headers.
 */

const STORAGE_KEY_API_KEY = "sakina_gemini_api_key";
const STORAGE_KEY_MODEL = "sakina_gemini_model";

export const DEFAULT_MODEL = "gemini-2.0-flash";

export const SUPPORTED_MODELS = [
  {
    id: "gemini-2.0-flash",
    name: "Gemini 2.0 Flash (Recommended)",
    description: "Google AI Studio flagship — high speed, exceptional emotional synthesis",
    recommended: true,
  },
  {
    id: "gemini-1.5-flash",
    name: "Gemini 1.5 Flash",
    description: "Fast, versatile, and highly reliable for everyday reflections",
    recommended: false,
  },
  {
    id: "gemini-1.5-pro",
    name: "Gemini 1.5 Pro",
    description: "Deep psychological & spiritual reasoning and nuanced reflection",
    recommended: false,
  },
  {
    id: "gemini-2.5-flash",
    name: "Gemini 2.5 Flash (Preview)",
    description: "Latest generation preview model for supported developer keys",
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
    const stored = localStorage.getItem(STORAGE_KEY_MODEL);
    if (stored && SUPPORTED_MODELS.some((m) => m.id === stored)) {
      return stored;
    }
    // Automatically migrate legacy or invalid stored model to DEFAULT_MODEL
    localStorage.setItem(STORAGE_KEY_MODEL, DEFAULT_MODEL);
    return DEFAULT_MODEL;
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

// In-flight request map for deduplicating concurrent GET/read requests
const inFlightRequests = new Map();

/**
 * Enhanced fetch wrapper that automatically attaches the user's
 * Gemini API Key, Gemini Model, and X-User-Id (if available) headers,
 * applies a 25-second AbortController timeout, and deduplicates in-flight reads.
 */
export async function apiFetch(url, options = {}, timeoutMs = 25000) {
  const method = (options.method || "GET").toUpperCase();
  const bodyKey = options.body ? (typeof options.body === "string" ? options.body : JSON.stringify(options.body)) : "";
  const requestKey = `${method}:${url}:${bodyKey}`;

  if (method === "GET" && inFlightRequests.has(requestKey)) {
    return inFlightRequests.get(requestKey);
  }

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

  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort(new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s`));
  }, timeoutMs);

  if (options.signal) {
    options.signal.addEventListener("abort", () => controller.abort());
  }

  const fetchPromise = (async () => {
    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });
      return response;
    } finally {
      clearTimeout(timeoutId);
      inFlightRequests.delete(requestKey);
    }
  })();

  if (method === "GET") {
    inFlightRequests.set(requestKey, fetchPromise);
  }

  return fetchPromise;
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
