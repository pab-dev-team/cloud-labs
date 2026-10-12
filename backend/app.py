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
            "SELECT id, title, ingredients, instructions, is_builtin FROM recipes ORDER BY id DESC"
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
    recipe["is_builtin"] = False
    return jsonify(recipe), 201


@app.route("/api/recipes/<int:recipe_id>", methods=["PUT", "DELETE"])
def change_recipe(recipe_id):
    recipe = read_recipe() if request.method == "PUT" else None
    with get_db() as db, db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT is_builtin FROM recipes WHERE id = %s FOR UPDATE", (recipe_id,))
        existing = cursor.fetchone()
        if existing is None:
            abort(404, description="Рецепт не найден.")
        if existing["is_builtin"]:
            abort(403, description="Начальные рецепты нельзя редактировать или удалять.")
        if request.method == "DELETE":
            cursor.execute("DELETE FROM recipes WHERE id = %s", (recipe_id,))
            db.commit()
            return jsonify(deleted=recipe_id)
        cursor.execute(
            "UPDATE recipes SET title = %s, ingredients = %s, instructions = %s WHERE id = %s",
            (recipe["title"], recipe["ingredients"], recipe["instructions"], recipe_id),
        )
        db.commit()
    return jsonify(id=recipe_id, is_builtin=False, **recipe)


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
    """Create the recipe table and seed an empty collection."""
    seeds = (
        (
            "Овсяная каша с яблоком",
            "Овсяные хлопья — 50 г\nМолоко — 200 мл\nЯблоко — 1 шт.\nКорица — по вкусу",
            "1. Доведите молоко до кипения.\n2. Добавьте хлопья и варите 5–7 минут, помешивая.\n"
            "3. Нарежьте яблоко и добавьте в кашу.\n4. Посыпьте корицей и подавайте.",
        ),
        (
            "Омлет с помидорами",
            "Яйца — 2 шт.\nМолоко — 2 ст. л.\nПомидор — 1 шт.\nМасло — 1 ч. л.\nСоль — по вкусу",
            "1. Взбейте яйца с молоком и солью.\n2. Нарежьте помидор.\n"
            "3. Разогрейте масло на сковороде и обжарьте помидор 2 минуты.\n"
            "4. Влейте яичную смесь и готовьте под крышкой до полной готовности яиц.",
        ),
        (
            "Паста с томатным соусом",
            "Паста — 200 г\nТоматы в собственном соку — 300 г\nЧеснок — 2 зубчика\n"
            "Оливковое масло — 1 ст. л.\nСоль и базилик — по вкусу",
            "1. Отварите пасту по инструкции на упаковке.\n"
            "2. Измельчите чеснок и прогрейте в масле 30 секунд.\n"
            "3. Добавьте томаты и тушите 10 минут.\n4. Посолите, добавьте базилик и смешайте с пастой.",
        ),
    )
    try:
        with get_db() as db, db.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS recipes ("
                "id INT AUTO_INCREMENT PRIMARY KEY, "
                "title VARCHAR(255) NOT NULL, "
                "ingredients TEXT NOT NULL, "
                "instructions TEXT NOT NULL, "
                "is_builtin BOOLEAN NOT NULL DEFAULT FALSE"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
            cursor.execute("SHOW COLUMNS FROM recipes LIKE 'is_builtin'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE recipes ADD COLUMN is_builtin BOOLEAN NOT NULL DEFAULT FALSE")
            # Legacy seeds were inserted first; matching their content preserves user recipes.
            cursor.executemany(
                "UPDATE recipes SET is_builtin = TRUE WHERE id = %s "
                "AND title = %s AND ingredients = %s AND instructions = %s",
                [(recipe_id, *recipe) for recipe_id, recipe in enumerate(seeds, 1)],
            )
            cursor.execute("SELECT COUNT(*) FROM recipes")
            if cursor.fetchone()[0] == 0:
                cursor.executemany(
                    "INSERT INTO recipes (title, ingredients, instructions, is_builtin) VALUES (%s, %s, %s, TRUE)",
                    seeds,
                )
            db.commit()
    except mysql.connector.Error as error:
        raise click.ClickException(
            "Не удалось подготовить БД. Проверьте MySQL и переменные окружения."
        ) from error
    click.echo("Таблица рецептов готова. Начальные рецепты добавлены, если таблица была пустой.")
