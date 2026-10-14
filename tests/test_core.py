"""
Self-contained tests.  Run from the project root:

    python -m unittest discover -s tests -v

Tests that need an optional package (bcrypt, python-jose, starlette) skip
themselves when it is not installed, so the suite runs everywhere. None of them
need a database or network.
"""

import ast
import asyncio
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("JWT_SECRET_KEY", "unit-test-secret-" + "x" * 40)
os.environ.setdefault("FOOTY254_DB_PASSWORD", "unit-test")
os.environ.setdefault("FRONTEND_URL", "https://app.example.com")


def has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


class PasswordPolicy(unittest.TestCase):
    def setUp(self):
        from security.password_policy import validate_password

        self.v = validate_password

    def test_rejects_weak(self):
        for pw in ["short", "12345678", "Password123", "footy254"]:
            self.assertIsNotNone(self.v(pw), pw)

    def test_rejects_personal(self):
        self.assertIsNotNone(self.v("johnsmith99", email="johnsmith@x.com"))
        self.assertIsNotNone(self.v("alicewonder!1", username="alicewonder"))

    def test_rejects_over_72_bytes(self):
        self.assertIsNotNone(self.v("é" * 40))

    def test_accepts_good(self):
        self.assertIsNone(self.v("correct horse battery"))


@unittest.skipUnless(has("bcrypt"), "bcrypt not installed")
class Hashing(unittest.TestCase):
    def test_roundtrip_and_legacy_hash(self):
        import bcrypt

        from security.hashing import hash_password, needs_rehash, verify_password

        h = hash_password("S3cure-pass!")
        self.assertTrue(verify_password("S3cure-pass!", h))
        self.assertFalse(verify_password("wrong", h))
        self.assertFalse(verify_password("x", "not-a-hash"))

        # A hash produced by the old passlib setup is plain $2b$ bcrypt.
        legacy = bcrypt.hashpw(b"old-password", bcrypt.gensalt(rounds=10)).decode()
        self.assertTrue(verify_password("old-password", legacy))
        self.assertTrue(needs_rehash(legacy))


@unittest.skipUnless(has("jose"), "python-jose not installed")
class Jwt(unittest.TestCase):
    def test_access_and_refresh(self):
        from security.jwt_handler import (
            create_access_token,
            create_refresh_token,
            decode_access_token,
            decode_refresh_token,
        )

        access = create_access_token(7)
        self.assertEqual(decode_access_token(access)["sub"], 7)
        self.assertIsNone(decode_refresh_token(access), "type confusion")

        refresh, jti, _ = create_refresh_token(7)
        self.assertEqual(decode_refresh_token(refresh)["jti"], jti)
        self.assertIsNone(decode_access_token(refresh), "type confusion")

    def test_garbage_and_tampering(self):
        from security.jwt_handler import create_access_token, decode_access_token

        self.assertIsNone(decode_access_token("not.a.jwt"))
        self.assertIsNone(decode_access_token(""))
        self.assertIsNone(decode_access_token(create_access_token(1)[:-3] + "abc"))


@unittest.skipUnless(has("starlette"), "starlette not installed")
class OriginGuard(unittest.TestCase):
    def run_guard(self, method, path, headers):
        from security.http_guards import OriginGuardMiddleware

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        out = []

        async def send(message):
            out.append(message)

        scope = {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
        }
        asyncio.run(OriginGuardMiddleware(app)(scope, None, send))
        return out[0]["status"]

    def test_blocks_cross_site_with_cookie(self):
        h = {"cookie": "footy254_access_token=a", "host": "app.example.com"}
        self.assertEqual(self.run_guard("POST", "/api/x", {**h, "origin": "https://evil.test"}), 403)
        self.assertEqual(self.run_guard("POST", "/api/x", {**h, "origin": "https://app.example.com"}), 200)
        self.assertEqual(self.run_guard("GET", "/api/x", {**h, "origin": "https://evil.test"}), 200)
        self.assertEqual(
            self.run_guard("POST", "/api/mpesa/callback/s", {**h, "origin": "https://evil.test"}), 200
        )


class RouteOrder(unittest.TestCase):
    """A '/{match_id}' route declared before fixed paths swallows them."""

    def test_fixed_paths_precede_parameter_route(self):
        for module in ("api/fixtures.py", "api/predictions.py"):
            tree = ast.parse((ROOT / module).read_text())
            paths = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for deco in node.decorator_list:
                        if isinstance(deco, ast.Call) and deco.args and isinstance(deco.args[0], ast.Constant):
                            paths.append((node.lineno, deco.args[0].value))
            paths.sort()
            ordered = [p for _, p in paths]
            if "/{match_id}" in ordered:
                self.assertEqual(ordered[-1], "/{match_id}", f"{module}: {ordered}")


class PredictionEngine(unittest.TestCase):
    """Runs the real shipped model: catches feature/training drift."""

    @classmethod
    def setUpClass(cls):
        if not all(has(m) for m in ("numpy", "pandas", "sklearn", "joblib")):
            raise unittest.SkipTest("ML dependencies not installed")

        from ml_pipeline.core.model_loader import load_all_cached
        from ml_pipeline.core.predict_engine import PredictionEngine as Engine

        a = load_all_cached()
        cls.engine = Engine(a["model"], a["scaler"], a["encoder"], a["elo"], a["team_stats"])
        cls.teams = list(a["encoder"].classes_)

    def test_features_match_trained_columns(self):
        import joblib

        cols = joblib.load(ROOT / "ml_pipeline" / "models" / "feature_columns.pkl")
        self.assertEqual(len(cols), 75)

    def test_prediction_is_valid_distribution(self):
        result = self.engine.predict(self.teams[0], self.teams[1])
        p = result["probabilities"]
        self.assertIn(result["prediction"], {"HOME", "DRAW", "AWAY"})
        self.assertAlmostEqual(p["home_win"] + p["draw"] + p["away_win"], 100.0, delta=0.5)

    def test_unknown_team_does_not_crash(self):
        self.assertIsNotNone(self.engine.predict(self.teams[0], "Nonexistent FC"))


class PoolProxy(unittest.TestCase):
    """Pool bookkeeping verified against a fake driver (no database needed)."""

    def setUp(self):
        class Conn:
            closed = 0

            def cursor(self, *a, **k):
                raise NotImplementedError

            def commit(self):
                self.committed = True

            def rollback(self):
                pass

        class Pool:
            def __init__(self, *a, **k):
                self.free = []

            def getconn(self):
                return self.free.pop() if self.free else Conn()

            def putconn(self, c, key=None, close=False):
                if not close:
                    self.free.append(c)

            def closeall(self):
                pass

        pg = types.ModuleType("psycopg2")
        pg.connect = lambda **k: Conn()
        pg.pool = types.ModuleType("psycopg2.pool")
        pg.pool.ThreadedConnectionPool = Pool
        pg.extras = types.ModuleType("psycopg2.extras")
        pg.extras.RealDictCursor = object
        self.saved = {k: sys.modules.get(k) for k in ("psycopg2", "psycopg2.pool", "psycopg2.extras")}
        sys.modules.update({"psycopg2": pg, "psycopg2.pool": pg.pool, "psycopg2.extras": pg.extras})
        sys.modules.pop("database.db_config", None)

        from database import db_config

        self.db = db_config

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        sys.modules.pop("database.db_config", None)

    def test_with_block_returns_connection_once(self):
        with self.db.get_connection() as conn:
            inner = conn._conn
        self.assertTrue(inner.committed)
        self.assertIn(inner, self.db._pool.free)
        conn.close()  # idempotent
        self.assertEqual(self.db._slots._value, self.db.settings.DB_POOL_MAX)

    def test_garbage_collected_connection_is_returned(self):
        import gc

        conn = self.db.get_connection()
        del conn
        gc.collect()
        self.assertEqual(self.db._slots._value, self.db.settings.DB_POOL_MAX)


if __name__ == "__main__":
    unittest.main()
