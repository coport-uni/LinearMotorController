# Probe a running rail server (read-only): hit the GET endpoints and
# print what comes back. Useful to confirm the server is up and the rail
# is being polled, without moving anything. Non-actuating.
#
# Usage: python3 claude_test/poke_server.py [BASE_URL]
#   BASE_URL defaults to http://localhost:17052

import json
import sys
import urllib.error
import urllib.request

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:17052"
GET_PATHS = ["/health", "/status"]


def get(path):
    url = BASE_URL + path
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = json.loads(response.read().decode())
            print(f"GET {path} -> {response.status}")
            print(json.dumps(body, indent=2))
    except urllib.error.HTTPError as exc:
        print(f"GET {path} -> HTTP {exc.code}: {exc.read().decode()}")
    except urllib.error.URLError as exc:
        print(f"GET {path} -> connection failed: {exc.reason}")
    print()


def main():
    print(f"probing {BASE_URL}\n")
    for path in GET_PATHS:
        get(path)


if __name__ == "__main__":
    main()
