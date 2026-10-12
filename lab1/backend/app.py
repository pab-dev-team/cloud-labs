import os
from pathlib import Path

import click
import mysql.connector
from flask import Flask, abort, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException


FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="/static")
app.config.update(
    MYSQL_HOST=os.environ.get("MYSQL_HOST", "127.0.0.1"),
    MYSQL_PORT=int(os.environ.get("MYSQL_PORT", "3306")),
    MYSQL_DATABASE=os.environ.get("MYSQL_DATABASE", "recipes"),
    MYSQL_USER=os.environ.get("MYSQL_USER", "recipes_app"),
    MYSQL_PASSWORD=os.environ.get("MYSQL_PASSWORD", ""),
    MAX_CONTENT_LENGTH=128 * 1024,
)
app.json.ensure_ascii = False

@app.after_request
def identify_backend(response):
    response.headers["X-Backend-ID"] = os.environ.get("BACKEND_ID", "local")
    return response


def get_db():
    return mysql.connector.connect(
        host=app.config["MYSQL_HOST"],
        port=app.config["MYSQL_PORT"],
        database=app.config["MYSQL_DATABASE"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        charset="utf8mb4",
        connection_timeout=5,
    )


@app.get("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.get("/api/recipes")
def list_recipes():
    with get_db() as db, db.cursor(dictionary=True) as cursor:
        cursor.execute(
            "SELECT id, title, ingredients, instructions FROM recipes ORDER BY id DESC"
        )
        return jsonify(cursor.fetchall())


def read_recipe():
    if not request.is_json:
        abort(415, description="Отправьте рецепт в формате JSON.")

    data = request.get_json()
    if not isinstance(data, dict):
        abort(400, description="Рецепт должен быть JSON-объектом.")

    recipe = {}
    for field, label, limit in (
        ("title", "Название", 255),
        ("ingredients", "Ингредиенты", 10000),
        ("instructions", "Шаги приготовления", 10000),
    ):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            abort(400, description=f'Заполните поле «{label}».')
        value = value.strip()
        if len(value) > limit:
            abort(400, description=f'Поле «{label}»: максимум {limit} символов.')
        recipe[field] = value
    return recipe


@app.post("/api/recipes")
def add_recipe():
    recipe = read_recipe()

    with get_db() as db, db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO recipes (title, ingredients, instructions) VALUES (%s, %s, %s)",
            (recipe["title"], recipe["ingredients"], recipe["instructions"]),
        )
        recipe["id"] = cursor.lastrowid
        db.commit()
    return jsonify(recipe), 201


@app.route("/api/recipes/<int:recipe_id>", methods=["PUT", "DELETE"])
def change_recipe(recipe_id):
    recipe = read_recipe() if request.method == "PUT" else None
    with get_db() as db, db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT id FROM recipes WHERE id = %s FOR UPDATE", (recipe_id,))
        existing = cursor.fetchone()
        if existing is None:
            abort(404, description="Рецепт не найден.")
        if request.method == "DELETE":
            cursor.execute("DELETE FROM recipes WHERE id = %s", (recipe_id,))
            db.commit()
            return jsonify(deleted=recipe_id)
        cursor.execute(
            "UPDATE recipes SET title = %s, ingredients = %s, instructions = %s WHERE id = %s",
            (recipe["title"], recipe["ingredients"], recipe["instructions"], recipe_id),
        )
        db.commit()
    return jsonify(id=recipe_id, **recipe)


@app.errorhandler(mysql.connector.Error)
def database_error(error):
    app.logger.exception("MySQL request failed")
    return jsonify(error="База данных недоступна. Попробуйте позже."), 503


@app.errorhandler(HTTPException)
def http_error(error):
    response = error.get_response()
    response.data = app.json.dumps({"error": error.description})
    response.content_type = "application/json"
    return response


@app.cli.command("init-db")
def init_db():
    """Create the recipe table without adding recipes."""
    try:
        with get_db() as db, db.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS recipes ("
                "id INT AUTO_INCREMENT PRIMARY KEY, "
                "title VARCHAR(255) NOT NULL, "
                "ingredients TEXT NOT NULL, "
                "instructions TEXT NOT NULL"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
            db.commit()
    except mysql.connector.Error as error:
        raise click.ClickException(
            "Не удалось подготовить БД. Проверьте MySQL и переменные окружения."
        ) from error
    click.echo("Таблица рецептов готова. Рецепты добавляются только через форму.")
