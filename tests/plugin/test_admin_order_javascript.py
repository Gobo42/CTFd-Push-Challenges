import subprocess
from pathlib import Path


def test_browser_checkbox_defaults_persists_restores_and_keeps_selections():
    harness = r"""
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { runInNewContext } = require("node:vm");
const source = readFileSync(process.argv[1], "utf8");

function page(store, blocked = false, scope = "/", present = true) {
  const nodes = new Map();
  const data = { order: [3, 1, 2], storageKey: `test-order:${scope}` };
  let writes = 0;
  const rows = [1, 2, 3].map(id => ({
    id, checkbox: { checked: id === 2 },
    querySelector: () => ({ dataset: { challengeId: String(id) } }),
  }));
  const body = {
    rows: [...rows],
    append(...ordered) { this.rows = ordered; writes++; },
  };
  const parent = { before: element => { parent.control = element; } };
  const table = {
    tBodies: [body],
    parentElement: parent,
    before: parent.before,
    querySelectorAll: () => rows,
  };
  function element(tag) {
    return {
      tagName: tag, children: [], checked: false, textContent: "",
      listeners: {}, style: {},
      append(...children) { this.children.push(...children); },
      setAttribute(name, value) { this[name] = value; },
      addEventListener(name, listener) { this.listeners[name] = listener; },
      set id(value) { this._id = value; nodes.set(value, this); },
      get id() { return this._id; },
    };
  }
  const document = {
    readyState: "complete",
    getElementById(id) {
      if (!present) return null;
      if (id === "challenges") return table;
      if (id === "push-challenges-admin-order-data") {
        return { textContent: JSON.stringify(data) };
      }
      return nodes.get(id) || null;
    },
    createElement: element,
  };
  const localStorage = {
    getItem(key) {
      if (blocked) throw Error("blocked");
      return store.get(key) || null;
    },
    setItem(key, value) { if (blocked) throw Error("blocked"); store.set(key, value); },
  };
  runInNewContext(source, { document, localStorage });
  const checkbox = nodes.get("push-challenges-group-order");
  function toggle(checked) { checkbox.checked = checked; checkbox.listeners.change(); }
  return { checkbox, body, rows, toggle, nodes, writes: () => writes };
}

const store = new Map();
let current = page(store);
assert.equal(current.checkbox.checked, false);
assert.equal(current.writes(), 0, "Unchecked initial state must not move rows");
assert.deepEqual(current.body.rows.map(row => row.id), [1, 2, 3]);
current.toggle(true);
assert.deepEqual(current.body.rows.map(row => row.id), [3, 1, 2]);
assert.equal(current.body.rows.find(row => row.id === 2).checkbox.checked, true);
current = page(store);
assert.equal(current.checkbox.checked, true, "Same browser must remember state");
assert.deepEqual(current.body.rows.map(row => row.id), [3, 1, 2]);
assert.equal(page(new Map()).checkbox.checked, false, "Another browser stays off");
assert.equal(page(store, false, "/other").checkbox.checked, false, "Per CTFd path");
current.toggle(false);
assert.deepEqual(current.body.rows.map(row => row.id), [1, 2, 3]);
assert.equal(page(store).checkbox.checked, false, "Disabled state must also persist");
const blocked = page(store, true);
assert.equal(blocked.checkbox.checked, false);
blocked.toggle(true);
assert.deepEqual(blocked.body.rows.map(row => row.id), [3, 1, 2]);
assert.match(
  blocked.nodes.get("push-challenges-order-status").textContent, /remember/i
);
blocked.toggle(false);
assert.deepEqual(blocked.body.rows.map(row => row.id), [1, 2, 3]);
page(new Map(), false, "/", false);
"""
    path = Path(__file__).resolve().parents[2] / "assets" / "admin-order.js"
    result = subprocess.run(
        ["node", "--eval", harness, str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
