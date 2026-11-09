import sys
import urllib.request
import json

def test_endpoint(name, url, method="GET", body=None):
    print(f"\n--- Testing {name} ---")
    try:
        req = urllib.request.Request(url, method=method)
        if body:
            req.add_header("Content-Type", "application/json")
            req.data = json.dumps(body).encode("utf-8")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
            print(f"  Status: {r.status}")
            if isinstance(data, dict) and "teams" in data:
                print(f"  Teams count: {len(data['teams'])}")
                print(f"  First 5: {data['teams'][:5]}")
            else:
                print(f"  Response: {json.dumps(data, indent=2)[:500]}")
    except Exception as e:
        print(f"  Error: {e}")

test_endpoint("GET /teams", "http://127.0.0.1:8000/teams")
test_endpoint("POST /predict", "http://127.0.0.1:8000/predict", "POST", {"home_team": "Liverpool FC", "away_team": "Arsenal FC"})
test_endpoint("GET /model/status", "http://127.0.0.1:8000/model/status")
