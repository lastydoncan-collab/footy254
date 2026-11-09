import sys
import time
import urllib.request
import json

def main():
    print("Testing local API /matches via HTTP GET...")
    start = time.time()
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/matches", method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode('utf-8')
            elapsed = time.time() - start
            print(f"Request succeeded in {elapsed:.4f}s")
            data = json.loads(body)
            print(f"Number of matches returned: {len(data.get('matches', []))}")
            if data.get('matches'):
                print("First match:")
                print(json.dumps(data['matches'][0], indent=2))
    except Exception as e:
        print(f"Request failed in {time.time() - start:.4f}s: {e}")

if __name__ == "__main__":
    main()
