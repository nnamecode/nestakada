(() => {
  "use strict";

  const makeButton = (label, attribute, value = "") => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute("data-price-input", "");
    button.setAttribute(attribute, value);
    return button;
  };

  const makeLabelInput = (label) => {
    const wrapper = document.createElement("label");
    wrapper.append(`${label} `);
    const input = document.createElement("input");
    input.required = true;
    input.maxLength = 500;
    input.setAttribute("data-price-input", "");
    input.setAttribute("data-price-label", "");
    wrapper.append(input);
    return wrapper;
  };

  const makeCell = (columnId) => {
    const cell = document.createElement("div");
    cell.setAttribute("data-price-cell", "");
    cell.dataset.priceColumnId = columnId;

    const kindLabel = document.createElement("label");
    kindLabel.append("Тип ");
    const kind = document.createElement("select");
    kind.setAttribute("data-price-input", "");
    kind.setAttribute("data-price-kind", "");
    [["", "Нет значения"], ["text", "Текст"], ["amount", "Сумма"]].forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      kind.append(option);
    });
    kindLabel.append(kind);

    const textFields = document.createElement("label");
    textFields.hidden = true;
    textFields.setAttribute("data-price-text-fields", "");
    textFields.append("Текст ");
    const text = document.createElement("input");
    text.maxLength = 1000;
    text.setAttribute("data-price-input", "");
    text.setAttribute("data-price-text", "");
    textFields.append(text);

    const amountFields = document.createElement("span");
    amountFields.hidden = true;
    amountFields.setAttribute("data-price-amount-fields", "");
    const amountLabel = document.createElement("label");
    amountLabel.append("Сумма ");
    const amount = document.createElement("input");
    amount.inputMode = "decimal";
    amount.setAttribute("data-price-input", "");
    amount.setAttribute("data-price-amount", "");
    amountLabel.append(amount);
    const fromLabel = document.createElement("label");
    fromLabel.append("От ");
    const from = document.createElement("input");
    from.type = "checkbox";
    from.setAttribute("data-price-input", "");
    from.setAttribute("data-price-from", "");
    fromLabel.append(from);
    amountFields.append(amountLabel, fromLabel);
    cell.append(kindLabel, textFields, amountFields);
    return cell;
  };

  document.querySelectorAll("[data-editor-form]").forEach((form) => {
    const control = form.querySelector("[data-price-control]");
    if (!control) return;
    try {
      if (!window.isSecureContext || typeof window.crypto?.randomUUID !== "function") {
        throw new Error("uuid-unavailable");
      }
      const columns = control.querySelector("[data-price-columns]");
      const rows = control.querySelector("[data-price-rows]");
      const changed = control.querySelector("[data-price-changed]");
      const carriers = control.querySelector("[data-price-carriers]");
      const save = form.querySelector("[data-editor-save]");
      if (!columns || !rows || !changed || !carriers || !save) throw new Error("price-shape");

      const showError = () => {
        form.setAttribute("data-editor-error", "1");
        form.querySelector("[data-editor-error-message]").hidden = false;
      };
      const markDirty = () => {
        changed.value = "1";
        if (
          form.hasAttribute("data-prices-only")
          && form.dataset.priceReady === "1"
          && form.dataset.editorReady === "1"
        ) save.disabled = false;
      };
      const direct = (root, selector) => [...root.querySelectorAll(`:scope > ${selector}`)];
      const exactLabel = (label, selector) => {
        if (!label || label.children.length !== 1 || direct(label, selector).length !== 1) {
          throw new Error("price-shape");
        }
      };
      const assertColumn = (column) => {
        const labels = direct(column, "label");
        const moves = direct(column, "[data-price-move]");
        const removes = direct(column, "[data-price-remove]");
        if (column.children.length !== 4 || labels.length !== 1 || moves.length !== 2 || removes.length !== 1) {
          throw new Error("price-shape");
        }
        exactLabel(labels[0], "[data-price-label]");
        if (moves.some((button) => button.children.length) || removes[0].children.length) throw new Error("price-shape");
      };
      const assertCell = (cell) => {
        const children = [...cell.children];
        if (
          children.length !== 3
          || children[0].tagName !== "LABEL"
          || children[1].tagName !== "LABEL"
          || !children[1].hasAttribute("data-price-text-fields")
          || children[2].tagName !== "SPAN"
          || !children[2].hasAttribute("data-price-amount-fields")
        ) throw new Error("price-shape");
        exactLabel(children[0], "[data-price-kind]");
        exactLabel(children[1], "[data-price-text]");
        const amountLabels = direct(children[2], "label");
        if (children[2].children.length !== 2 || amountLabels.length !== 2) throw new Error("price-shape");
        exactLabel(amountLabels[0], "[data-price-amount]");
        exactLabel(amountLabels[1], "[data-price-from]");
      };
      const assertRow = (row) => {
        const labels = direct(row, "label");
        const moves = direct(row, "[data-price-move]");
        const removes = direct(row, "[data-price-remove]");
        const cellContainers = direct(row, "[data-price-cells]");
        if (
          row.children.length !== 5
          || labels.length !== 1
          || moves.length !== 2
          || removes.length !== 1
          || cellContainers.length !== 1
        ) throw new Error("price-shape");
        exactLabel(labels[0], "[data-price-label]");
        if (moves.some((button) => button.children.length) || removes[0].children.length) throw new Error("price-shape");
        const cells = direct(cellContainers[0], "[data-price-cell]");
        if (cells.length !== cellContainers[0].children.length) throw new Error("price-shape");
        cells.forEach(assertCell);
      };
      const syncCell = (cell) => {
        const kind = cell.querySelector("[data-price-kind]").value;
        cell.querySelector("[data-price-text-fields]").hidden = kind !== "text";
        cell.querySelector("[data-price-amount-fields]").hidden = kind !== "amount";
      };
      const bindCell = (cell) => {
        cell.querySelector("[data-price-kind]").addEventListener("change", () => {
          syncCell(cell);
          markDirty();
        });
        syncCell(cell);
      };
      const bindMoveRemove = (item, container, kind) => {
        item.querySelectorAll("[data-price-move]").forEach((button) => button.addEventListener("click", () => {
          const sibling = button.dataset.priceMove === "up" ? item.previousElementSibling : item.nextElementSibling;
          if (!sibling) return;
          if (button.dataset.priceMove === "up") container.insertBefore(item, sibling);
          else container.insertBefore(sibling, item);
          if (kind === "column") {
            const order = [...columns.querySelectorAll(":scope > [data-price-column]")].map((node) => node.dataset.priceId);
            rows.querySelectorAll("[data-price-row]").forEach((row) => {
              const cellContainer = row.querySelector("[data-price-cells]");
              order.forEach((id) => cellContainer.append(cellContainer.querySelector(`[data-price-column-id="${id}"]`)));
            });
          }
          markDirty();
        }));
        item.querySelector("[data-price-remove]").addEventListener("click", () => {
          if (kind === "column") {
            const id = item.dataset.priceId;
            rows.querySelectorAll(`[data-price-cell][data-price-column-id="${id}"]`).forEach((cell) => cell.remove());
          }
          item.remove();
          markDirty();
        });
      };
      const bindColumn = (column) => {
        assertColumn(column);
        bindMoveRemove(column, columns, "column");
      };
      const bindRow = (row) => {
        assertRow(row);
        bindMoveRemove(row, rows, "row");
        row.querySelectorAll("[data-price-cell]").forEach(bindCell);
      };

      const initialColumns = direct(columns, "[data-price-column]");
      const initialRows = direct(rows, "[data-price-row]");
      if (initialColumns.length !== columns.children.length || initialRows.length !== rows.children.length) {
        throw new Error("price-shape");
      }
      initialColumns.forEach(bindColumn);
      initialRows.forEach(bindRow);
      control.querySelector("[data-price-add-column]").addEventListener("click", () => {
        if (columns.children.length >= 32) return;
        const id = window.crypto.randomUUID();
        const column = document.createElement("div");
        column.setAttribute("data-price-column", "");
        column.dataset.priceId = id;
        column.append(
          makeLabelInput("Колонка"),
          makeButton("←", "data-price-move", "up"),
          makeButton("→", "data-price-move", "down"),
          makeButton("Удалить колонку", "data-price-remove"),
        );
        columns.append(column);
        rows.querySelectorAll("[data-price-row]").forEach((row) => {
          const cell = makeCell(id);
          row.querySelector("[data-price-cells]").append(cell);
          bindCell(cell);
        });
        bindColumn(column);
        markDirty();
      });
      control.querySelector("[data-price-add-row]").addEventListener("click", () => {
        if (rows.children.length >= 500) return;
        const row = document.createElement("section");
        row.setAttribute("data-price-row", "");
        row.dataset.priceId = window.crypto.randomUUID();
        const cells = document.createElement("div");
        cells.setAttribute("data-price-cells", "");
        columns.querySelectorAll("[data-price-column]").forEach((column) => cells.append(makeCell(column.dataset.priceId)));
        row.append(
          makeLabelInput("Строка"),
          makeButton("↑", "data-price-move", "up"),
          makeButton("↓", "data-price-move", "down"),
          makeButton("Удалить строку", "data-price-remove"),
          cells,
        );
        rows.append(row);
        bindRow(row);
        markDirty();
      });
      control.addEventListener("input", markDirty);
      control.addEventListener("change", markDirty);
      form.addEventListener("submit", (event) => {
        try {
          carriers.replaceChildren();
          if (changed.value !== "1") return;
          const records = [];
          const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
          const plain = (value, cap, empty = false) => {
            if (
              (!empty && value.length === 0)
              || [...value].length > cap
              || value !== value.normalize("NFC")
              || value.includes("\t")
              || /[\u0000-\u001f\u007f]/u.test(value)
            ) throw new Error("price-control");
            return value;
          };
          const identifier = (value) => {
            if (!uuidPattern.test(value)) throw new Error("price-uuid");
            return value;
          };
          const addRecord = (name, value) => {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = name;
            input.value = value;
            records.push(input);
          };
          const columnItems = [...columns.querySelectorAll(":scope > [data-price-column]")];
          const rowItems = [...rows.querySelectorAll(":scope > [data-price-row]")];
          if (
            columnItems.length !== columns.children.length
            || rowItems.length !== rows.children.length
          ) throw new Error("price-shape");
          if (columnItems.length > 32 || rowItems.length > 500) throw new Error("price-cap");
          columnItems.forEach(assertColumn);
          rowItems.forEach(assertRow);
          const columnIds = columnItems.map((item) => identifier(item.dataset.priceId));
          if (new Set(columnIds).size !== columnIds.length) throw new Error("price-column");
          columnItems.forEach((item) => addRecord("price.column", `${item.dataset.priceId}\t${plain(item.querySelector("[data-price-label]").value, 500)}`));
          let cellCount = 0;
          const rowIds = rowItems.map((row) => identifier(row.dataset.priceId));
          if (new Set(rowIds).size !== rowIds.length || rowIds.some((id) => columnIds.includes(id))) throw new Error("price-row");
          rowItems.forEach((row) => {
            addRecord("price.row", `${row.dataset.priceId}\t${plain(row.querySelector("[data-price-label]").value, 500)}`);
            const cellContainer = row.querySelector("[data-price-cells]");
            const directCells = [...cellContainer.querySelectorAll(":scope > [data-price-cell]")];
            if (directCells.length !== cellContainer.children.length || directCells.length !== columnIds.length) {
              throw new Error("price-cell");
            }
            columnIds.forEach((columnId) => {
              const matches = directCells.filter((item) => item.dataset.priceColumnId === columnId);
              if (matches.length !== 1) throw new Error("price-cell");
              const [cell] = matches;
              if (!cell) throw new Error("price-cell");
              const kind = cell.querySelector("[data-price-kind]").value;
              if (!kind) return;
              cellCount += 1;
              if (cellCount > 10000) throw new Error("price-cap");
              if (kind === "text") {
                addRecord("price.cell", `${row.dataset.priceId}\t${columnId}\ttext\t${plain(cell.querySelector("[data-price-text]").value, 1000, true)}`);
              } else if (kind === "amount") {
                const amount = plain(cell.querySelector("[data-price-amount]").value, 12);
                if (!/^(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,2})?$/u.test(amount)) throw new Error("price-amount");
                addRecord("price.cell", `${row.dataset.priceId}\t${columnId}\tamount\t${amount}\t${cell.querySelector("[data-price-from]").checked ? "1" : "0"}`);
              } else throw new Error("price-kind");
            });
          });
          carriers.append(...records);
        } catch (_error) {
          event.preventDefault();
          showError();
        }
      });
      control.querySelectorAll("[data-price-input]").forEach((input) => { input.disabled = false; });
      form.dataset.priceReady = "1";
    } catch (_error) {
      form.setAttribute("data-editor-error", "1");
      const message = form.querySelector("[data-editor-error-message]");
      if (message) message.hidden = false;
    }
  });
})();
