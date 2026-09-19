// 사용자 노출 문구 금지 표현 목록. copy-rules.test.ts가 app/·lib/의 문자열을 이 목록으로 검사한다.
// 출처: AGENTS.md "사용자 노출 표현 규칙"(재점검 신호·근거 서술)과 모델 지표 오표기.

export interface CopyRule {
  pattern: RegExp;
  reason: string;
}

export const FORBIDDEN_COPY: readonly CopyRule[] = [
  { pattern: /지금\s*(사|파)세요/, reason: "매매 지시 (AGENTS.md 재점검 신호)" },
  { pattern: /(매수|매도)\s*하세요/, reason: "매매 지시 (AGENTS.md 재점검 신호)" },
  { pattern: /비중을\s*낮게\s*가져가/, reason: "비중 권고 (AGENTS.md 재점검 신호)" },
  { pattern: /신규\s*진입은\s*신중/, reason: "진입 권고 (AGENTS.md 재점검 신호)" },
  { pattern: /(오를|내릴)\s*것/, reason: "수익률 전망 (AGENTS.md 근거 서술)" },
  { pattern: /적중률/, reason: "모델 지표(ROC-AUC 등)를 적중률로 오표기할 수 있는 용어" },
  { pattern: /정확도\s*[\d{$]/, reason: "'정확도 N%' 표기 (ROC-AUC 오표기)" },
];
