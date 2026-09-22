import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { FORBIDDEN_COPY } from "./copy-rules.ts";

const ROOT = path.resolve(import.meta.dirname, "..");

// 검사하지 않는 파일과 이유.
const EXCLUDED = new Set([
  "lib/copy-rules.ts", // 금지 표현 목록 자체
  "lib/providers/sentiment-fixture.ts", // 실제 기사 제목(외부 데이터)이라 우리 문구가 아니다
  "lib/profiling/bit.ts", // composite 등 분류 계산의 정의 파일(화면 문구 없음)
]);

// "계산 근거" 영역: 이 표시 사이의 줄은 개발 용어를 쓸 수 있다.
const EXEMPT_START = "copy-rules:계산근거 시작";
const EXEMPT_END = "copy-rules:계산근거 끝";

function sourceFiles(dir: string): string[] {
  return readdirSync(path.join(ROOT, dir), { withFileTypes: true, recursive: true })
    .filter((entry) => entry.isFile() && /\.tsx?$/.test(entry.name) && !entry.name.includes(".test."))
    .map((entry) => path.relative(ROOT, path.join(entry.parentPath, entry.name)))
    .filter((file) => !EXCLUDED.has(file));
}

// 주석은 사용자에게 보이지 않으므로 지운다. 줄 번호를 지키려고 블록 주석의 줄바꿈은 남긴다.
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, (block) => block.replace(/[^\n]/g, ""))
    .replace(/(^|[^:"'`\\])\/\/.*$/gm, "$1");
}

test("사용자 노출 문구에 금지 표현이 없다", () => {
  const hits: string[] = [];
  for (const file of [...sourceFiles("app"), ...sourceFiles("lib")]) {
    const raw = readFileSync(path.join(ROOT, file), "utf8");
    const rawLines = raw.split("\n");
    const lines = stripComments(raw).split("\n");
    let exempt = false;
    lines.forEach((line, index) => {
      if (rawLines[index].includes(EXEMPT_START)) exempt = true;
      if (rawLines[index].includes(EXEMPT_END)) exempt = false;
      if (exempt) return;
      for (const { pattern, reason } of FORBIDDEN_COPY) {
        if (pattern.test(line)) hits.push(`${file}:${index + 1} ${reason} — ${line.trim()}`);
      }
    });
  }
  assert.deepEqual(hits, []);
});

test("금지 표현 목록이 대표 문장을 잡는다", () => {
  const caught = (text: string) => FORBIDDEN_COPY.some(({ pattern }) => pattern.test(text));
  for (const text of [
    "지금 사세요",
    "지금 파세요",
    "비중을 낮게 가져가는 것을 권장합니다",
    "신규 진입은 신중히",
    "오를 것으로 보입니다",
    "적중률 61%",
    "정확도 64%",
    "정확도 {auc}",
    "오늘의 추천 종목",
    "넛지",
    "H10 · 10거래일 후",
    "68% 신뢰구간",
    "Supabase 조회값",
    "composite +0.2",
  ]) {
    assert.ok(caught(text), text);
  }
  assert.ok(!caught("과거 유사 신호 중 상승 비율 61%"));
  assert.ok(!caught("getSupabaseClient()"));
  assert.ok(!caught("const h10 = agreement.h10"));
});
