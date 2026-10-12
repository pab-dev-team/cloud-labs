const recipes = document.querySelector("#recipes");
const count = document.querySelector("#recipe-count");
const listStatus = document.querySelector("#list-status");
const form = document.querySelector("#recipe-form");
const formStatus = document.querySelector("#form-status");
const submit = document.querySelector("#submit-recipe");
const template = document.querySelector("#recipe-template");
const formTitle = document.querySelector("#form-title");
const submitLabel = document.querySelector("#submit-label");
const cancelEdit = document.querySelector("#cancel-edit");
const deleteDialog = document.querySelector("#delete-dialog");
let editingId = null;

async function requestRecipes(options, id) {
  let response;
  try {
    response = await fetch(id === undefined ? "/api/recipes" : `/api/recipes/${id}`, options);
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
  const card = template.content.firstElementChild.cloneNode(true);
  card.dataset.id = recipe.id;
  card.querySelector(".recipe-number").textContent = `РЕЦЕПТ № ${recipe.id}`;
  card.querySelector(".recipe-title").textContent = recipe.title;
  card.querySelector(".recipe-ingredients").textContent = recipe.ingredients;
  card.querySelector(".recipe-instructions").textContent = recipe.instructions;
  card.querySelector(".recipe-actions").hidden = Boolean(recipe.is_builtin);
  card.querySelector(".edit-recipe").addEventListener("click", () => {
    editingId = recipe.id;
    for (const field of ["title", "ingredients", "instructions"]) {
      form.elements[field].value = recipe[field];
    }
    formTitle.textContent = "Редактировать рецепт";
    submitLabel.textContent = "Сохранить изменения";
    cancelEdit.hidden = false;
    formStatus.textContent = "";
    formStatus.classList.remove("error");
    form.elements.title.focus();
  });
  card.querySelector(".delete-recipe").addEventListener("click", () => {
    document.querySelector("#delete-description").textContent = `Рецепт «${recipe.title}» будет удалён.`;
    deleteDialog.returnValue = "cancel";
    deleteDialog.addEventListener("close", async () => {
      if (deleteDialog.returnValue !== "delete") return;
      setBusy(true);
      listStatus.classList.remove("error");
      try {
        await requestRecipes({ method: "DELETE" }, recipe.id);
        card.remove();
        if (editingId === recipe.id) {
          resetEditor();
          formStatus.textContent = "Рецепт удалён.";
        }
        updateCount();
      } catch (error) {
        listStatus.textContent = error.message;
        listStatus.classList.add("error");
      } finally {
        setBusy(false);
      }
    }, { once: true });
    deleteDialog.showModal();
  });
  return card;
}

function setBusy(busy) {
  for (const control of form.elements) control.disabled = busy;
  for (const button of recipes.querySelectorAll("button")) button.disabled = busy;
}

function resetEditor() {
  editingId = null;
  form.reset();
  formTitle.textContent = "Ваш рецепт";
  submitLabel.textContent = "Сохранить рецепт";
  cancelEdit.hidden = true;
  formStatus.textContent = "";
  formStatus.classList.remove("error");
}

cancelEdit.addEventListener("click", resetEditor);

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
  if (submit.disabled) return;
  const id = editingId;
  const payload = JSON.stringify(Object.fromEntries(new FormData(form)));
  formStatus.textContent = "Сохраняем…";
  formStatus.classList.remove("error");
  setBusy(true);

  try {
    const recipe = await requestRecipes({
      method: id === null ? "POST" : "PUT",
      headers: { "Content-Type": "application/json" },
      body: payload,
    }, id === null ? undefined : id);
    if (id === null) {
      recipes.prepend(recipeCard(recipe));
    } else {
      recipes.querySelector(`[data-id="${id}"]`).replaceWith(recipeCard(recipe));
    }
    listStatus.classList.remove("error");
    updateCount();
    resetEditor();
    formStatus.textContent = id === null ? "Рецепт сохранён. Можно готовить!" : "Изменения сохранены.";
  } catch (error) {
    formStatus.textContent = error.message;
    formStatus.classList.add("error");
  } finally {
    setBusy(false);
  }
});

loadRecipes();
