# 검토한 디자인 스킬 (허용 목록)

`AGENTS.md` "검토한 디자인 스킬 허용 목록"의 실물이다. 원본 레포의 `SKILL.md`를 **고치지 않고** 복사했고
(각 README가 허용하는 설치 방법), 라이선스(MIT)를 같은 폴더에 둔다. 미러·포크본은 쓰지 않는다.

| 스킬 | 원본 | 커밋 SHA | 쓰는 곳 |
|---|---|---|---|
| `redesign-existing-projects` | https://github.com/Leonxlnx/taste-skill `skills/redesign-skill` | `5217fb45be2c0b302f29c9cd31cbd3237501c684` | 기존 화면 진단 |
| `minimalist-ui` | https://github.com/Leonxlnx/taste-skill `skills/minimalist-skill` | `5217fb45be2c0b302f29c9cd31cbd3237501c684` | 절제된 표면·타이포 원칙 |
| `baseline-ui` | https://github.com/ibelick/ui-skills `skills/baseline-ui` | `b1cc8e0073ac64b09b3d38cd604407aa20c2b7ad` | 간격·위계·빈 상태 점검 |
| `fixing-motion-performance` | https://github.com/ibelick/ui-skills `skills/fixing-motion-performance` | `b1cc8e0073ac64b09b3d38cd604407aa20c2b7ad` | 모션 점검 |
| `frontend-design` | https://github.com/anthropics/skills `skills/frontend-design` (Apache-2.0) | `33375500bcea98d610eb30ce10ac4e59b89c390d` | 새 화면 기획(브리프 → 토큰 계획 → 기본값 점검 → 구현 → 스크린샷 자기 비판) |

## 우선순위

**AGENTS.md > frontend/DESIGN.md > 스킬.** 스킬 지시가 우리 규칙(표현 규칙, 색의 의미, 화이트박스, 결정론)과
부딪히면 우리 규칙을 따른다. 알려진 충돌과 판정:

| 스킬 지시 | 판정 | 이유 |
|---|---|---|
| minimalist-ui: 스크롤 등장·순차 등장 애니메이션, 배경 이미지·그레인·그라데이션 광원 | 기각 | DESIGN.md 5장 — 모션은 펼치기/닫기 피드백에만 |
| minimalist-ui: 세리프 제목, Inter 금지, Phosphor 아이콘 | 기각 | 한글 본문은 Pretendard 하나. 아이콘 라이브러리 추가 없음 |
| minimalist-ui: 파스텔 알약 배지 | 기각 | 알약 배지 남발 금지, 색은 가격 방향에만 |
| redesign: 폰트 교체(Geist 등), 노이즈·스포트라이트 테두리, 3열 카드 금지 | 기각 | 한글 폰트·금융 대시보드 맥락과 맞지 않음 |
| redesign: 글래스모피즘 | 부분 채택(2026-09-26) | 탐색 층(헤더·하단 탭 막대·팝오버)에만. 데이터 면은 불투명 유지. DESIGN.md 4-1 |
| frontend-design: "제품을 드러내는 과감한 선택 하나", 브리프 대조, 스크린샷 자기 비판, 가짜 01/02/03 금지, 전부 대문자 라벨 금지 | 채택 | 과감함은 유리 탭 막대 한 곳에 쓰고 나머지는 조용히 |
| frontend-design: 메타 문자열을 가운뎃점(`A · B`)으로 잇지 말 것, 제목 위 eyebrow 라벨 줄이기 | 기각 / 부분 채택 | 가운뎃점 회색 한 줄은 알약 배지 남발을 막는 우리 규칙(DESIGN.md 4장). eyebrow는 섹션 머리에만 |
| frontend-design: 기본값이 아닌 서체 고르기 | 기각 | 한글 본문은 Pretendard 하나 |
| redesign: 가짜 숫자를 "자연스럽게" 흩트리기 | 기각 | 없는 데이터를 만들지 않는다. 예시는 예시로 표시 |
| baseline-ui: motion/react·cn·Radix/Base UI 도입 | 기각 | 새 의존성 추가 없이 기존 스택(Tailwind v4 + 네이티브 요소)으로 |
| baseline-ui: 자간 변경 금지 | 부분 채택 | 제목 자간 -0.02em은 유지(한글 큰 글자 보정) |
| 공통: 강조색 하나, 그라데이션·글로우 금지, 빈 상태에 다음 행동 하나, tabular-nums, 200ms 이하 ease-out, prefers-reduced-motion | 채택 | DESIGN.md v2에 반영 |

taste-skill의 다이얼(DESIGN_VARIANCE·MOTION_INTENSITY·VISUAL_DENSITY)은 본체 스킬(`design-taste-frontend`) 설정이라
설치하지 않았다. 판단 기준으로만 **DESIGN_VARIANCE=3, MOTION_INTENSITY=2, VISUAL_DENSITY=5**를 쓴다
(가운데 정렬·절제된 레이아웃, 호버·펼치기 정도의 모션, 대시보드치고 여유 있는 밀도).
`high-end-visual-design`, `industrial-brutalist-ui`는 금융 대시보드와 맞지 않아 쓰지 않는다.

## 검토했지만 설치하지 않은 도구 (2026-09-23)

| 도구 | 판정 | 이유 |
|---|---|---|
| [ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | 기각 | 스타일 79종·팔레트 192종 중 고르는 도구. 우리는 스타일을 이미 정했다(DESIGN.md). 로고·이미지 생성은 범위 밖 |
| [awesome-claude-design](https://github.com/VoltAgent/awesome-claude-design) | 아이디어만 | Apple DESIGN.md와 대조했다. 절제 원칙(강조색 하나, 카드 그림자 없음, 면으로 구분)은 이미 같다. 빠진 터치 영역 규칙만 DESIGN.md 3장에 추가 |
| [design-md-chrome](https://github.com/bergside/design-md-chrome) | 기각 | 남의 사이트 스타일을 통째로 뽑아 오는 도구. 우리는 성균관대 색 + 자체 규칙이라 뽑아 올 대상이 없다 |
| [design-motion-principles](https://github.com/kylezantos/design-motion-principles) | 기각 | 우리 모션은 펼치기·눌림 피드백뿐(DESIGN.md 5장). `fixing-motion-performance`로 충분 |
| Claude Code `/design` | 사용 | 기본 기능(Pro 이상, 추가 비용 없음). 새 화면은 구현 전에 `/design`으로 시안을 여러 개 뽑아 고른다. 시안도 DESIGN.md를 따른다 |

## 검토했지만 설치하지 않은 도구 (2026-09-26)

| 도구 | 판정 | 이유 |
|---|---|---|
| [superpowers](https://github.com/obra/superpowers) (MIT) | 개인 선택 | 질문 → 설계 승인 → 짧은 계획 → 테스트 먼저. 서환이 이미 개인 설치로 쓰고 있다(`docs/superpowers/`). 단계마다 문서를 만들어 토큰을 많이 쓰므로 레포 공용 설치는 하지 않는다 |
| [ponytail](https://github.com/DietrichGebert/ponytail) (MIT) | 사용 중 | 중현 세션에 이미 켜져 있다(#136 정리). "라이브러리 대신 네이티브 한 줄" 원칙은 DESIGN.md의 새 의존성 금지와 같다 |
| 클레이모피즘·뉴모피즘·스큐어모피즘 | 기각 | 부푼 3D·낮은 대비·실물 흉내는 금융 근거 화면의 가독성·무게와 맞지 않는다. 유리는 탐색 층에만 채택(DESIGN.md 4-1) |
