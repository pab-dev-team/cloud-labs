import json
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

import mysql.connector

from backend.app import app, get_db


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_frontend_is_served(self):
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn('id="recipe-form"', response.get_data(as_text=True))
        for path in ("/static/app.js", "/static/style.css"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200)

    @patch("backend.app.get_db")
    def test_invalid_recipes_do_not_reach_database(self, connect):
        valid = {"title": "Суп", "ingredients": "Вода", "instructions": "Вскипятить"}
        invalid = [None, [], "recipe", {}, {**valid, "title": "   "}]
        for field, limit in (("title", 255), ("ingredients", 10000), ("instructions", 10000)):
            invalid.extend(({**valid, field: 42}, {**valid, field: "я" * (limit + 1)}))
        for payload in invalid:
            with self.subTest(payload=str(payload)[:80]):
                response = self.client.post(
                    "/api/recipes", data=json.dumps(payload), content_type="application/json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json)
        connect.assert_not_called()

    def test_only_json_posts_are_accepted(self):
        response = self.client.post("/api/recipes", data={"title": "Суп"})
        self.assertEqual(response.status_code, 415)
        response = self.client.post("/api/recipes", data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            "/api/recipes", data="x" * (128 * 1024 + 1), content_type="application/json"
        )
        self.assertEqual(response.status_code, 413)
        response = self.client.put("/api/recipes", json={})
        self.assertEqual(response.status_code, 405)
        self.assertIn("GET", response.headers["Allow"])
        self.assertIn("POST", response.headers["Allow"])

    @patch("backend.app.get_db", side_effect=mysql.connector.Error("private connection details"))
    def test_database_failure_has_safe_response(self, connect):
        with self.assertLogs(app.logger, level="ERROR"):
            response = self.client.get("/api/recipes")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private connection details", response.get_data(as_text=True))


@unittest.skipUnless(os.environ.get("MYSQL_TEST_DATABASE"), "Set MYSQL_TEST_DATABASE for real MySQL checks")
class MySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database = os.environ["MYSQL_TEST_DATABASE"]
        if not database.endswith("_test"):
            raise ValueError("MYSQL_TEST_DATABASE must end with _test to protect application data")
        cls.original_database = app.config["MYSQL_DATABASE"]
        app.config["MYSQL_DATABASE"] = database
        cls.addClassCleanup(app.config.update, MYSQL_DATABASE=cls.original_database)
        result = app.test_cli_runner().invoke(args=["init-db"])
        if result.exit_code:
            raise RuntimeError(result.output)

    def test_seed_is_repeatable_and_recipe_survives_new_connection(self):
        client = app.test_client()
        initial = client.get("/api/recipes")
        self.assertEqual(initial.status_code, 200)
        self.assertGreaterEqual(len(initial.json), 3)
        result = app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(client.get("/api/recipes").json, initial.json)

        payload = {
            "title": f"  Рецепт {uuid4()} 🍲 '; DROP TABLE recipes; --  ",
            "ingredients": "Яблоко — 1 шт.\nВода — 100 мл",
            "instructions": "<script>alert('test')</script>\n1. Смешать.",
        }
        response = client.post("/api/recipes", json=payload)
        self.assertEqual(response.status_code, 201)
        recipe_id = response.json["id"]
        try:
            with get_db() as db, db.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM recipes WHERE id = %s", (recipe_id,))
                stored = cursor.fetchone()
            expected = {key: value.strip() for key, value in payload.items()}
            self.assertEqual(stored, {"id": recipe_id, **expected})
            recipes = app.test_client().get("/api/recipes").json
            self.assertIn(stored, recipes)
        finally:
            with get_db() as db, db.cursor() as cursor:
                cursor.execute("DELETE FROM recipes WHERE id = %s", (recipe_id,))
                db.commit()


if __name__ == "__main__":
    unittest.main()
