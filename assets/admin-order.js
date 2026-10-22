(() => {
  const table = document.getElementById("challenges");
  const data = document.getElementById("push-challenges-admin-order-data");
  if (!table || !table.tBodies[0] || !data ||
      document.getElementById("push-challenges-group-order")) return;

  const config = JSON.parse(data.textContent);
  const original = Array.from(table.querySelectorAll("tbody tr[data-href]"));
  const rank = new Map(config.order.map((id, index) => [String(id), index]));
  const rowRank = row =>
    rank.get(row.querySelector("[data-challenge-id]").dataset.challengeId);
  const grouped = [...original].sort((left, right) => rowRank(left) - rowRank(right));

  const control = document.createElement("div");
  control.className = "mb-2";
  const label = document.createElement("label");
  label.className = "d-flex align-items-center mb-0";
  label.style.minHeight = "44px";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.id = "push-challenges-group-order";
  checkbox.className = "mr-2";
  checkbox.setAttribute("aria-describedby", "push-challenges-order-status");
  const text = document.createElement("span");
  text.textContent = "Group by category and position";
  label.append(checkbox, text);
  const status = document.createElement("div");
  status.id = "push-challenges-order-status";
  status.className = "small text-muted";
  status.setAttribute("role", "status");
  status.textContent = "Saved only in this browser. Position 0 sorts last in each category.";
  control.append(label, status);
  table.before(control);

  const applyOrder = () => {
    table.tBodies[0].append(...(checkbox.checked ? grouped : original));
    status.textContent = checkbox.checked
      ? "Grouped by category, then position. Position 0 sorts last."
      : "Normal CTFd order restored.";
  };

  try {
    checkbox.checked = localStorage.getItem(config.storageKey) === "1";
  } catch {
    checkbox.checked = false;
    status.textContent = "Browser storage is blocked; this choice cannot be remembered.";
  }
  if (checkbox.checked) applyOrder();

  checkbox.addEventListener("change", () => {
    applyOrder();
    try {
      localStorage.setItem(config.storageKey, checkbox.checked ? "1" : "0");
    } catch {
      status.textContent += " This choice cannot be remembered; it applies only to this page.";
    }
  });
})();
