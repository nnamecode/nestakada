"use strict";

(() => {
  const tags = new Set([
    "p", "br", "h2", "h3", "blockquote", "ul", "ol", "li", "strong", "em", "u", "s",
    "sub", "sup", "a", "table", "caption", "thead", "tbody", "tr", "th", "td",
  ]);
  const attributes = {a: ["href", "title"], th: ["colspan", "rowspan", "scope"], td: ["colspan", "rowspan"]};
  const blocks = new Set(["p", "h2", "h3", "blockquote", "li"]);
  const inline = new Set(["strong", "em", "u", "s"]);
  const text = (value) => value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  const attribute = (value) => text(value).replaceAll('"', "&quot;");

  function validHref(value) {
    if (value.startsWith("https://")) {
      try {
        const parsed = new URL(value);
        return parsed.protocol === "https:" && parsed.hostname.split(".").length >= 2
          && /^[A-Za-z0-9.-]+$/u.test(parsed.hostname) && !parsed.username && !parsed.password
          && !parsed.port && !parsed.hash && !parsed.pathname.includes("\\");
      } catch (_error) { return false; }
    }
    if (!value.startsWith("/") || value.startsWith("//") || /[\\\s]/u.test(value)
        || value.includes("#") || /%(?![0-9A-Fa-f]{2})/u.test(value)) return false;
    const [path, query = ""] = value.split("?", 2);
    if (!["", "page=1", "page=2"].includes(query)) return false;
    try {
      const decoded = decodeURIComponent(path);
      return !/[\\\s\u0000-\u001f\u007f]/u.test(decoded)
        && !decoded.split("/").some((part) => part === "." || part === "..");
    } catch (_error) { return false; }
  }

  function serialize(node) {
    if (node.nodeType === Node.TEXT_NODE) return text(node.nodeValue || "");
    if (node.nodeType !== Node.ELEMENT_NODE) throw new Error("unsupported-node");
    const tag = node.tagName.toLowerCase();
    if (!tags.has(tag)) throw new Error("unsupported-tag");
    const order = attributes[tag] || [];
    const permitted = new Set(order);
    for (const item of node.attributes) {
      if (!permitted.has(item.name)) throw new Error("unsupported-attribute");
      if (item.name === "href" && !validHref(item.value)) throw new Error("unsafe-link");
      if (["rowspan", "colspan"].includes(item.name)
          && !/^(?:[1-9]|[1-9][0-9]|100)$/u.test(item.value)) throw new Error("table-span");
      if (item.name === "scope" && !["row", "col"].includes(item.value)) throw new Error("table-scope");
    }
    const items = order.map((name) => node.getAttributeNode(name)).filter(Boolean);
    const encoded = items.map((item) => ` ${item.name}="${attribute(item.value)}"`).join("");
    if (tag === "br") return `<br${encoded}>`;
    return `<${tag}${encoded}>${[...node.childNodes].map(serialize).join("")}</${tag}>`;
  }

  function selectedRange(editor) {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount !== 1) return null;
    const range = selection.getRangeAt(0);
    return editor.contains(range.commonAncestorContainer) ? range : null;
  }

  function closest(node, editor, predicate) {
    let current = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
    while (current && current !== editor) {
      if (predicate(current)) return current;
      current = current.parentElement;
    }
    return null;
  }

  function wrap(range, tag) {
    const element = document.createElement(tag);
    element.append(range.extractContents());
    range.insertNode(element);
  }

  function replaceBlock(range, editor, tag) {
    const current = closest(range.startContainer, editor, (item) => blocks.has(item.tagName.toLowerCase()));
    if (!current) throw new Error("block-required");
    const replacement = document.createElement(tag);
    replacement.append(...current.childNodes);
    current.replaceWith(replacement);
  }

  function makeList(range, editor, tag) {
    const current = closest(range.startContainer, editor, (item) => blocks.has(item.tagName.toLowerCase()));
    if (!current) throw new Error("block-required");
    const list = document.createElement(tag);
    const item = document.createElement("li");
    item.append(...current.childNodes);
    list.append(item);
    current.replaceWith(list);
  }

  function placeCaret(node) {
    const range = document.createRange();
    range.selectNodeContents(node);
    range.collapse(true);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  document.querySelectorAll("[data-editor-form]").forEach((form) => {
    const controls = [...form.querySelectorAll("[data-rich-control]")];
    const save = form.querySelector("[data-editor-save]");
    const errorMessage = form.querySelector("[data-editor-error-message]");
    const showError = () => { form.setAttribute("data-editor-error", "1"); errorMessage.hidden = false; };
    const markDirty = (control) => { control.querySelector("[data-rich-changed]").value = "1"; };
    for (const control of controls) {
      const editor = control.querySelector("[data-rich-editor]");
      editor.contentEditable = "true";
      editor.addEventListener("input", () => markDirty(control));
      editor.addEventListener("beforeinput", (event) => {
        if (!["insertParagraph", "insertLineBreak"].includes(event.inputType)) return;
        const range = selectedRange(editor);
        if (!range) return;
        event.preventDefault();
        range.deleteContents();
        if (event.inputType === "insertLineBreak") {
          const lineBreak = document.createElement("br");
          range.insertNode(lineBreak);
          range.setStartAfter(lineBreak);
          range.collapse(true);
        } else {
          const paragraph = document.createElement("p");
          paragraph.append(document.createElement("br"));
          const block = closest(range.startContainer, editor, (item) => blocks.has(item.tagName.toLowerCase()));
          if (block) block.after(paragraph); else editor.append(paragraph);
          placeCaret(paragraph);
        }
        markDirty(control);
      });
      editor.addEventListener("paste", (event) => {
        event.preventDefault();
        const range = selectedRange(editor);
        const pasted = event.clipboardData?.getData("text/plain");
        if (!range || pasted === undefined) return;
        range.deleteContents();
        const fragment = document.createDocumentFragment();
        pasted.split(/\r?\n/u).forEach((line, index) => {
          if (index) fragment.append(document.createElement("br"));
          fragment.append(document.createTextNode(line));
        });
        range.insertNode(fragment);
        markDirty(control);
      });
      control.querySelectorAll("[data-rich-action]").forEach((button) => button.addEventListener("click", () => {
        const range = selectedRange(editor);
        if (!range) return;
        const action = button.dataset.richAction;
        try {
          if (inline.has(action)) wrap(range, action);
          else if (["p", "h2", "h3", "blockquote"].includes(action)) replaceBlock(range, editor, action);
          else if (["ul", "ol"].includes(action)) makeList(range, editor, action);
          else if (action === "link") {
            const href = window.prompt("Адрес ссылки");
            if (!href || !validHref(href)) throw new Error("unsafe-link");
            const anchor = document.createElement("a");
            anchor.href = href;
            anchor.append(range.extractContents());
            range.insertNode(anchor);
          } else if (action === "unlink") {
            const anchor = closest(range.startContainer, editor, (item) => item.tagName.toLowerCase() === "a");
            if (anchor) anchor.replaceWith(...anchor.childNodes);
          }
          markDirty(control);
        } catch (_error) { showError(); }
      }));
    }
    form.addEventListener("submit", (event) => {
      try {
        for (const control of controls) {
          if (control.querySelector("[data-rich-changed]").value !== "1") continue;
          const carrier = control.querySelector("[data-rich-value]");
          carrier.value = [...control.querySelector("[data-rich-editor]").childNodes].map(serialize).join("");
          carrier.disabled = false;
        }
      } catch (_error) {
        event.preventDefault();
        showError();
      }
    });
    const price = form.querySelector("[data-price-control]");
    const process = form.querySelector("[data-process-control]");
    const links = form.querySelector("[data-links-control]");
    form.dataset.editorReady = "1";
    if ((!price || form.dataset.priceReady === "1")
        && (!process || form.dataset.processReady === "1")
        && (!links || form.dataset.linksReady === "1")) {
      save.disabled = form.hasAttribute("data-prices-only")
        && price?.querySelector("[data-price-changed]").value !== "1";
    }
  });
})();
