(() => {
  "use strict";

  const one = (root, selector) => {
    const values = root.querySelectorAll(selector);
    if (values.length !== 1) throw new Error("links-shape");
    return values[0];
  };

  const plain = (value, cap) => (
    typeof value === "string"
    && value.length > 0
    && [...value].length <= cap
    && value.normalize("NFC") === value
    && !/[\u0000-\u001f\u007f]/u.test(value)
  );

  const makeInput = (attribute) => {
    const input = document.createElement("input");
    input.disabled = true;
    input.required = true;
    input.setAttribute("data-links-input", "");
    input.setAttribute(attribute, "");
    return input;
  };

  const makeButton = (label, attribute, value = "") => {
    const button = document.createElement("button");
    button.disabled = true;
    button.type = "button";
    button.textContent = label;
    button.setAttribute("data-links-input", "");
    button.setAttribute(attribute, value);
    return button;
  };

  const makeItem = () => {
    const item = document.createElement("div");
    item.setAttribute("data-links-item", "");
    const labelWrapper = document.createElement("label");
    labelWrapper.append("Название ", makeInput("data-links-label"));
    const urlWrapper = document.createElement("label");
    urlWrapper.append("HTTPS-адрес ", makeInput("data-links-url"));
    item.append(
      labelWrapper,
      urlWrapper,
      makeButton("↑", "data-links-move", "up"),
      makeButton("↓", "data-links-move", "down"),
      makeButton("Удалить ссылку", "data-links-remove"),
    );
    return item;
  };

  document.querySelectorAll("[data-editor-form]").forEach((form) => {
    const controls = form.querySelectorAll("[data-links-control]");
    if (controls.length === 0) return;
    try {
      if (controls.length !== 1) throw new Error("links-shape");
      const control = controls[0];
      const items = one(control, "[data-links-items]");
      const changed = one(control, "[data-links-changed]");
      const carriers = one(control, "[data-links-carriers]");
      const add = one(control, "[data-links-add]");
      const save = one(form, "[data-editor-save]");
      const errorMessage = one(form, "[data-editor-error-message]");
      if (changed.value !== "0" || carriers.children.length !== 0) throw new Error("links-shape");

      const showError = () => {
        form.setAttribute("data-editor-error", "1");
        errorMessage.hidden = false;
      };
      const outerShape = () => {
        if (
          control.children.length !== 5
          || control.children[0].tagName !== "H2"
          || control.children[1] !== changed
          || control.children[2] !== items
          || control.children[3] !== add
          || control.children[4] !== carriers
          || changed.tagName !== "INPUT"
          || changed.type !== "hidden"
          || changed.name !== "links.changed"
          || items.tagName !== "DIV"
          || carriers.tagName !== "DIV"
          || add.tagName !== "BUTTON"
          || add.type !== "button"
          || !add.hasAttribute("data-links-input")
        ) throw new Error("links-shape");
      };
      const directItems = () => {
        const values = [...items.children];
        if (values.length > 64 || values.some((item) => !item.hasAttribute("data-links-item"))) {
          throw new Error("links-shape");
        }
        if (control.querySelectorAll("[data-links-item]").length !== values.length) {
          throw new Error("links-shape");
        }
        return values;
      };
      const parts = (item) => {
        if (item.children.length !== 5) throw new Error("links-shape");
        const label = one(item, "[data-links-label]");
        const url = one(item, "[data-links-url]");
        const up = one(item, '[data-links-move="up"]');
        const down = one(item, '[data-links-move="down"]');
        const remove = one(item, "[data-links-remove]");
        if (
          item.querySelectorAll("[data-links-input]").length !== 5
          || label.tagName !== "INPUT"
          || url.tagName !== "INPUT"
          || label.type !== "text"
          || url.type !== "text"
          || !label.required
          || !url.required
          || [up, down, remove].some((button) => button.tagName !== "BUTTON" || button.type !== "button")
          || item.children[0].tagName !== "LABEL"
          || item.children[1].tagName !== "LABEL"
          || item.children[0].children.length !== 1
          || item.children[1].children.length !== 1
          || item.children[0].children[0] !== label
          || item.children[1].children[0] !== url
          || item.children[2] !== up
          || item.children[3] !== down
          || item.children[4] !== remove
        ) throw new Error("links-shape");
        return { label, url, up, down, remove };
      };
      const updateButtons = () => {
        const values = directItems();
        values.forEach((item, index) => {
          const controlsForItem = parts(item);
          controlsForItem.up.disabled = index === 0;
          controlsForItem.down.disabled = index === values.length - 1;
          controlsForItem.remove.disabled = false;
          controlsForItem.label.disabled = false;
          controlsForItem.url.disabled = false;
        });
        add.disabled = values.length >= 64;
      };
      const markDirty = () => { changed.value = "1"; };
      const bind = (item) => {
        const controlsForItem = parts(item);
        controlsForItem.label.addEventListener("input", markDirty);
        controlsForItem.url.addEventListener("input", markDirty);
        controlsForItem.up.addEventListener("click", () => {
          if (item.previousElementSibling) {
            item.previousElementSibling.before(item);
            markDirty();
            updateButtons();
          }
        });
        controlsForItem.down.addEventListener("click", () => {
          if (item.nextElementSibling) {
            item.nextElementSibling.after(item);
            markDirty();
            updateButtons();
          }
        });
        controlsForItem.remove.addEventListener("click", () => {
          item.remove();
          markDirty();
          updateButtons();
        });
      };

      directItems().forEach(bind);
      add.addEventListener("click", () => {
        if (directItems().length >= 64) return;
        const item = makeItem();
        items.append(item);
        bind(item);
        markDirty();
        updateButtons();
      });
      form.addEventListener("submit", (event) => {
        try {
          outerShape();
          const values = directItems().map((item) => {
            const controlsForItem = parts(item);
            if (!plain(controlsForItem.label.value, 500) || !plain(controlsForItem.url.value, 2048)) {
              throw new Error("links-value");
            }
            return `${controlsForItem.label.value}\t${controlsForItem.url.value}`;
          });
          carriers.replaceChildren();
          if (changed.value === "1") {
            const fragment = document.createDocumentFragment();
            values.forEach((value) => {
              const carrier = document.createElement("input");
              carrier.type = "hidden";
              carrier.name = "links.item";
              carrier.value = value;
              fragment.append(carrier);
            });
            carriers.append(fragment);
          } else if (changed.value !== "0") {
            throw new Error("links-changed");
          }
        } catch (_error) {
          event.preventDefault();
          carriers.replaceChildren();
          showError();
        }
      });
      outerShape();
      updateButtons();
      form.dataset.linksReady = "1";
    } catch (_error) {
      const errorMessage = form.querySelector("[data-editor-error-message]");
      form.setAttribute("data-editor-error", "1");
      if (errorMessage) errorMessage.hidden = false;
    }
  });
})();
