(() => {
  "use strict";

  const one = (root, selector) => {
    const values = root.querySelectorAll(selector);
    if (values.length !== 1) throw new Error("process-shape");
    return values[0];
  };

  const plain = (value, cap, empty) => (
    typeof value === "string"
    && (empty || value.length > 0)
    && [...value].length <= cap
    && value.normalize("NFC") === value
    && !/[\u0000-\u001f\u007f]/u.test(value)
  );

  const makeInput = (attribute, required) => {
    const input = document.createElement("input");
    input.disabled = true;
    input.required = required;
    input.setAttribute("data-process-input", "");
    input.setAttribute(attribute, "");
    return input;
  };

  const makeButton = (label, attribute, value = "") => {
    const button = document.createElement("button");
    button.disabled = true;
    button.type = "button";
    button.textContent = label;
    button.setAttribute("data-process-input", "");
    button.setAttribute(attribute, value);
    return button;
  };

  const makeStep = () => {
    const step = document.createElement("div");
    step.setAttribute("data-process-step", "");
    const titleLabel = document.createElement("label");
    titleLabel.append("Название ", makeInput("data-process-title", true));
    const bodyLabel = document.createElement("label");
    bodyLabel.append("Описание ", makeInput("data-process-body", false));
    step.append(
      titleLabel,
      bodyLabel,
      makeButton("↑", "data-process-move", "up"),
      makeButton("↓", "data-process-move", "down"),
      makeButton("Удалить этап", "data-process-remove"),
    );
    return step;
  };

  document.querySelectorAll("[data-editor-form]").forEach((form) => {
    const controls = form.querySelectorAll("[data-process-control]");
    if (controls.length === 0) return;
    try {
      if (controls.length !== 1) throw new Error("process-shape");
      const control = controls[0];
      const steps = one(control, "[data-process-steps]");
      const changed = one(control, "[data-process-changed]");
      const carriers = one(control, "[data-process-carriers]");
      const add = one(control, "[data-process-add]");
      const save = one(form, "[data-editor-save]");
      const errorMessage = one(form, "[data-editor-error-message]");
      if (changed.value !== "0" || carriers.children.length !== 0) throw new Error("process-shape");

      const outerShape = () => {
        if (
          control.children.length !== 5
          || control.children[0].tagName !== "H2"
          || control.children[1] !== changed
          || control.children[2] !== steps
          || control.children[3] !== add
          || control.children[4] !== carriers
          || changed.tagName !== "INPUT"
          || changed.type !== "hidden"
          || changed.name !== "process.changed"
          || steps.tagName !== "DIV"
          || carriers.tagName !== "DIV"
          || add.tagName !== "BUTTON"
          || add.type !== "button"
          || !add.hasAttribute("data-process-input")
        ) throw new Error("process-shape");
      };

      const showError = () => {
        form.setAttribute("data-editor-error", "1");
        errorMessage.hidden = false;
      };
      const directSteps = () => {
        const values = [...steps.children];
        if (values.length > 12 || values.some((item) => !item.hasAttribute("data-process-step"))) {
          throw new Error("process-shape");
        }
        if (control.querySelectorAll("[data-process-step]").length !== values.length) {
          throw new Error("process-shape");
        }
        return values;
      };
      const parts = (step) => {
        if (step.children.length !== 5) throw new Error("process-shape");
        const title = one(step, "[data-process-title]");
        const body = one(step, "[data-process-body]");
        const up = one(step, '[data-process-move="up"]');
        const down = one(step, '[data-process-move="down"]');
        const remove = one(step, "[data-process-remove]");
        const inputs = step.querySelectorAll("[data-process-input]");
        if (
          inputs.length !== 5
          || title.tagName !== "INPUT"
          || body.tagName !== "INPUT"
          || !title.required
          || body.required
          || title.type !== "text"
          || body.type !== "text"
          || [up, down, remove].some((item) => item.tagName !== "BUTTON" || item.type !== "button")
          || step.children[0].tagName !== "LABEL"
          || step.children[1].tagName !== "LABEL"
          || step.children[0].children.length !== 1
          || step.children[1].children.length !== 1
          || step.children[0].children[0] !== title
          || step.children[1].children[0] !== body
          || step.children[2] !== up
          || step.children[3] !== down
          || step.children[4] !== remove
        ) throw new Error("process-shape");
        return { title, body, up, down, remove };
      };
      const updateButtons = () => {
        const values = directSteps();
        values.forEach((step, index) => {
          const item = parts(step);
          item.up.disabled = index === 0;
          item.down.disabled = index === values.length - 1;
          item.remove.disabled = false;
          item.title.disabled = false;
          item.body.disabled = false;
        });
        add.disabled = values.length >= 12;
      };
      const markDirty = () => { changed.value = "1"; };
      const bind = (step) => {
        const item = parts(step);
        item.title.addEventListener("input", markDirty);
        item.body.addEventListener("input", markDirty);
        item.up.addEventListener("click", () => {
          if (step.previousElementSibling) {
            step.previousElementSibling.before(step);
            markDirty();
            updateButtons();
          }
        });
        item.down.addEventListener("click", () => {
          if (step.nextElementSibling) {
            step.nextElementSibling.after(step);
            markDirty();
            updateButtons();
          }
        });
        item.remove.addEventListener("click", () => {
          step.remove();
          markDirty();
          updateButtons();
        });
      };

      directSteps().forEach(bind);
      add.addEventListener("click", () => {
        if (directSteps().length >= 12) return;
        const step = makeStep();
        steps.append(step);
        bind(step);
        markDirty();
        updateButtons();
      });
      form.addEventListener("submit", (event) => {
        try {
          outerShape();
          const values = directSteps().map((step) => {
            const item = parts(step);
            if (!plain(item.title.value, 500, false) || !plain(item.body.value, 4000, true)) {
              throw new Error("process-value");
            }
            return `${item.title.value}\t${item.body.value}`;
          });
          carriers.replaceChildren();
          if (changed.value === "1") {
            const fragment = document.createDocumentFragment();
            values.forEach((value) => {
              const carrier = document.createElement("input");
              carrier.type = "hidden";
              carrier.name = "process.step";
              carrier.value = value;
              fragment.append(carrier);
            });
            carriers.append(fragment);
          } else if (changed.value !== "0") {
            throw new Error("process-changed");
          }
        } catch (_error) {
          event.preventDefault();
          carriers.replaceChildren();
          showError();
        }
      });
      outerShape();
      updateButtons();
      form.dataset.processReady = "1";
    } catch (_error) {
      const errorMessage = form.querySelector("[data-editor-error-message]");
      form.setAttribute("data-editor-error", "1");
      if (errorMessage) errorMessage.hidden = false;
    }
  });
})();
