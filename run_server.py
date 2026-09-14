import os
import uvicorn

if __name__ == "__main__":
    raw_port = os.environ.get("PORT", "").strip()
    port = int(raw_port) if raw_port and raw_port.isdigit() else 8000
    print(f"[System] Starting Sakina backend on port {port}...")
    uvicorn.run("FrontendAPI:app", host="0.0.0.0", port=port, reload=False)
