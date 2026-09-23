import assert from "node:assert/strict";
import { test } from "node:test";
import { migrateStorageKeys, STORAGE_KEYS } from "./storage-keys.ts";

function memoryStore(initial: Record<string, string>) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
  };
}

test("새 키가 없고 옛 키만 있으면 옮기고 옛 키를 지운다", () => {
  const store = memoryStore({ "signallab.ips-profile.v1": "P", "signallab.holdings.v1": "H" });
  migrateStorageKeys(store);
  assert.deepEqual(Object.fromEntries(store.data), {
    [STORAGE_KEYS.profile]: "P",
    [STORAGE_KEYS.holdings]: "H",
  });
});

test("둘 다 있으면 새 값을 유지하고 옛 키만 지운다", () => {
  const store = memoryStore({ "signallab.demo-session.v1": "old", [STORAGE_KEYS.demoSession]: "new" });
  migrateStorageKeys(store);
  assert.deepEqual(Object.fromEntries(store.data), { [STORAGE_KEYS.demoSession]: "new" });
});

test("여러 번 돌려도 결과가 같고, 관계없는 키는 건드리지 않는다", () => {
  const store = memoryStore({
    "signallab.survey-draft.v1": "D",
    "sb-abc-auth-token": "supabase",
    other: "x",
  });
  migrateStorageKeys(store);
  const once = Object.fromEntries(store.data);
  migrateStorageKeys(store);
  assert.deepEqual(Object.fromEntries(store.data), once);
  assert.deepEqual(once, { [STORAGE_KEYS.surveyDraft]: "D", "sb-abc-auth-token": "supabase", other: "x" });
});

test("빈 문자열 값도 값으로 옮긴다(없음과 구분)", () => {
  const store = memoryStore({ "signallab.holdings.v1": "" });
  migrateStorageKeys(store);
  assert.equal(store.getItem(STORAGE_KEYS.holdings), "");
});
