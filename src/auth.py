"""OAuth authentication for TickTick API."""

import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from base64 import b64encode
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN_FILE = Path(__file__).parent.parent / "tokens.json"
REDIRECT_URI = "http://localhost:8090/callback"
AUTH_URL = "https://ticktick.com/oauth/authorize"
TOKEN_URL = "https://ticktick.com/oauth/token"


def _basic_auth() -> str:
    creds = f"{os.environ['TICKTICK_CLIENT_ID']}:{os.environ['TICKTICK_CLIENT_SECRET']}"
    return b64encode(creds.encode()).decode()


def get_access_token() -> str:
    """Return valid access token, from env or tokens.json."""
    # Prefer env var
    token = os.environ.get("TICKTICK_ACCESS_TOKEN")
    if token:
        return token
    # Fall back to stored tokens
    if TOKEN_FILE.exists():
        data = json.loads(TOKEN_FILE.read_text())
        return data["access_token"]
    raise RuntimeError("No access token. Run: uv run python src/auth.py")


def _exchange_code(code: str) -> dict:
    resp = httpx.post(
        TOKEN_URL,
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
        headers={"Authorization": f"Basic {_basic_auth()}"},
    )
    resp.raise_for_status()
    return resp.json()


def authorize():
    """Run interactive OAuth flow — opens browser, captures callback."""
    params = urlencode({
        "client_id": os.environ["TICKTICK_CLIENT_ID"],
        "scope": "tasks:read tasks:write",
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
    })
    url = f"{AUTH_URL}?{params}"
    print(f"Opening browser for authorization...\n{url}")
    webbrowser.open(url)

    auth_code = None

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            qs = parse_qs(urlparse(self.path).query)
            auth_code = qs.get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorization complete. You can close this tab.")

        def log_message(self, *args):
            pass

    server = HTTPServer(("localhost", 8090), Handler)
    server.handle_request()

    if not auth_code:
        raise RuntimeError("No auth code received")

    tokens = _exchange_code(auth_code)
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    print(f"Tokens saved to {TOKEN_FILE}")


if __name__ == "__main__":
    authorize()
