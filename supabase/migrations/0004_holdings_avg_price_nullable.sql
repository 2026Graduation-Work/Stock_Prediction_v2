-- 0004: 보유 종목 평균 매입가를 선택 입력으로 (온보딩 "모르면 비워 두기")
-- 비어 있으면 화면은 기준일 종가 × 수량으로 비중을 계산하고 "현재가 기준"으로 표시한다.
-- RLS 정책·권한은 그대로 둔다(0001_init.sql). 여러 번 실행해도 안전하다.
alter table public.portfolio_holdings
  alter column avg_buy_price drop not null;

-- 기존 check (avg_buy_price >= 0)는 null을 통과시키므로 그대로 유효하다.
comment on column public.portfolio_holdings.avg_buy_price is
  '평균 매입가(원). null = 사용자가 모름 — 비중은 기준일 종가 기준';
