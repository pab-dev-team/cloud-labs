const recipes = document.querySelector("#recipes");
const count = document.querySelector("#recipe-count");
const listStatus = document.querySelector("#list-status");
const form = document.querySelector("#recipe-form");
const formStatus = document.querySelector("#form-status");
const submit = document.querySelector("#submit-recipe");
const template = document.querySelector("#recipe-template");

async function requestRecipes(options) {
  let response;
  try {
    response = await fetch("/api/recipes", options);
  } catch {
    throw new Error("Не удалось связаться с сервером. Проверьте список перед повторной отправкой.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.error || `Сервер вернул ошибку ${response.status}. Попробуйте позже.`);
  }
  if (data === null) {
    throw new Error("Сервер вернул некорректный ответ. Попробуйте позже.");
  }
  return data;
}

function recipeCard(recipe) {
  const card = template.content.cloneNode(true);
  card.querySelector(".recipe-number").textContent = `РЕЦЕПТ № ${recipe.id}`;
  card.querySelector(".recipe-title").textContent = recipe.title;
  card.querySelector(".recipe-ingredients").textContent = recipe.ingredients;
  card.querySelector(".recipe-instructions").textContent = recipe.instructions;
  return card;
}

function updateCount() {
  count.textContent = recipes.childElementCount;
  listStatus.textContent = recipes.childElementCount ? "" : "Пока нет рецептов. Добавьте первый через форму.";
}

async function loadRecipes() {
  try {
    const data = await requestRecipes();
    recipes.replaceChildren(...data.map(recipeCard));
    updateCount();
  } catch (error) {
    listStatus.textContent = error.message;
    listStatus.classList.add("error");
  } finally {
    submit.disabled = false;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formStatus.textContent = "Сохраняем…";
  formStatus.classList.remove("error");
  submit.disabled = true;

  try {
    const recipe = await requestRecipes({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    recipes.prepend(recipeCard(recipe));
    listStatus.classList.remove("error");
    updateCount();
    form.reset();
    formStatus.textContent = "Рецепт сохранён. Можно готовить!";
  } catch (error) {
    formStatus.textContent = error.message;
    formStatus.classList.add("error");
  } finally {
    submit.disabled = false;
  }
});

loadRecipes();
