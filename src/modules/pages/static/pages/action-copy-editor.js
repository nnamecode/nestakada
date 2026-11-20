(() => {
  "use strict";

  const one = (root, selector) => {
    const values = root.querySelectorAll(selector);
    if (values.length !== 1) throw new Error("actions-shape");
    return values[0];
  };

  document.querySelectorAll("[data-editor-form]").forEach((form) => {
    const controls = form.querySelectorAll("[data-actions-control]");
    if (controls.length === 0) return;
    try {
      if (controls.length !== 1) throw new Error("actions-shape");
      const control = controls[0];
      const cards = one(control, "[data-action-cards]");
      one(form, "[data-editor-save]");
      one(form, "[data-editor-error-message]");
      if (
        control.children.length !== 2
        || control.children[0].tagName !== "H2"
        || control.children[1] !== cards
        || cards.tagName !== "DIV"
      ) throw new Error("actions-shape");

      const directCards = [...cards.children];
      if (
        directCards.length > 32
        || control.querySelectorAll("[data-action-card]").length !== directCards.length
      ) throw new Error("actions-shape");

      const titles = directCards.map((card, index) => {
        if (
          card.tagName !== "SECTION"
          || !card.hasAttribute("data-action-card")
          || card.dataset.actionIndex !== String(index)
          || card.children.length !== 3
          || card.children[0].tagName !== "LABEL"
          || card.children[1].tagName !== "P"
        ) throw new Error("actions-shape");
        const title = one(card, "[data-action-title]");
        const url = one(card, "[data-action-url]");
        const body = one(card, "[data-action-body]");
        const changed = one(body, "[data-rich-changed]");
        const value = one(body, "[data-rich-value]");
        const editor = one(body, "[data-rich-editor]");
        if (
          card.children[0].children.length !== 1
          || card.children[0].children[0] !== title
          || card.children[1].children.length !== 1
          || card.children[1].children[0] !== url
          || card.children[2] !== body
          || title.tagName !== "INPUT"
          || title.type !== "text"
          || !title.required
          || !title.disabled
          || title.name !== `actions.${index}.title`
          || url.tagName !== "CODE"
          || body.tagName !== "SECTION"
          || !body.hasAttribute("data-rich-control")
          || body.children.length !== 5
          || body.children[0].tagName !== "H3"
          || body.children[1].tagName !== "DIV"
          || body.children[2] !== editor
          || editor.tagName !== "DIV"
          || body.children[3] !== changed
          || body.children[4] !== value
          || changed.tagName !== "INPUT"
          || changed.type !== "hidden"
          || changed.name !== `actions.${index}.body.changed`
          || changed.value !== "0"
          || value.tagName !== "TEXTAREA"
          || value.name !== `actions.${index}.body.value`
          || !value.disabled
        ) throw new Error("actions-shape");
        return title;
      });
      titles.forEach((title) => { title.disabled = false; });
      form.dataset.actionsReady = "1";
    } catch (_error) {
      const errorMessage = form.querySelector("[data-editor-error-message]");
      form.setAttribute("data-editor-error", "1");
      if (errorMessage) errorMessage.hidden = false;
    }
  });
})();
