import assert from "node:assert/strict";
import { test } from "node:test";
import {
  loadSupabaseFinancial,
  loadSupabaseSentiment,
} from "./supabase-insights.ts";

type Response = { data: unknown; error: { message: string } | null };

class FakeQuery implements PromiseLike<Response> {
  private readonly response: Response;
  readonly operations: Array<[string, ...unknown[]]>;

  constructor(response: Response, operations: Array<[string, ...unknown[]]>) {
    this.response = response;
    this.operations = operations;
  }

  select(...args: unknown[]) { this.operations.push(["select", ...args]); return this; }
  eq(...args: unknown[]) { this.operations.push(["eq", ...args]); return this; }
  not(...args: unknown[]) { this.operations.push(["not", ...args]); return this; }
  order(...args: unknown[]) { this.operations.push(["order", ...args]); return this; }
  limit(...args: unknown[]) { this.operations.push(["limit", ...args]); return this; }
  maybeSingle() { this.operations.push(["maybeSingle"]); return Promise.resolve(this.response); }
  then<TResult1 = Response, TResult2 = never>(
    onfulfilled?: ((value: Response) => TResult1 | PromiseLike<TResult1>) | null,
    onrejected?: ((reason: unknown) => TResult2 | PromiseLike<TResult2>) | null,
  ): PromiseLike<TResult1 | TResult2> {
    return Promise.resolve(this.response).then(onfulfilled, onrejected);
  }
}

class FakeClient {
  readonly operations: Record<string, Array<[string, ...unknown[]]>> = {};
  private readonly responses: Record<string, Response[]>;

  constructor(responses: Record<string, Response[]>) {
    this.responses = responses;
  }

  from(table: string) {
    const operations = (this.operations[table] ??= []);
    const response = this.responses[table]?.shift() ?? { data: [], error: null };
    return new FakeQuery(response, operations);
  }
}

const trackRows = [
  {
    stock_code: "005930",
    track: "historical",
    source: "bigkinds",
    backend: "kr-finbert",
    status: "ok",
    as_of: "2025-12-02T23:59:59+09:00",
    window_start: "2025-11-13",
    window_end: "2025-12-02",
    sentiment_mean: 0.2,
    sentiment_std: 0.3,
    article_count: 40,
    publisher_count: 4,
    fetched_count: 50,
    relevant_count: 40,
    newest_published_at: null,
    lag_minutes: null,
    provider_total_results: null,
    provider_returned_count: null,
    provider_pages: null,
    provider_truncated: false,
  },
  {
    stock_code: "005930",
    track: "live",
    source: "newsapi_ai",
    backend: "kr-finbert",
    status: "partial",
    as_of: "2026-09-26T09:00:00+09:00",
    window_start: "2026-09-25",
    window_end: "2026-09-26",
    sentiment_mean: 0.45,
    sentiment_std: 0.2,
    article_count: 12,
    publisher_count: 5,
    fetched_count: 100,
    relevant_count: 12,
    newest_published_at: "2026-09-26T08:40:00+09:00",
    lag_minutes: 20,
    provider_total_results: 120,
    provider_returned_count: 100,
    provider_pages: 2,
    provider_truncated: true,
  },
];

test("Supabase 감성은 최신 과거 20일과 live 요약·최신 기사 3건을 분리한다", async () => {
  const daily = Array.from({ length: 22 }, (_, index) => ({
    sentiment_date: `2025-11-${String(index + 1).padStart(2, "0")}`,
    status: "ok",
    sentiment_mean: index === 0 ? null : index / 100,
    sentiment_std: 0.1,
    article_count: index + 1,
    publisher_count: 2,
  })).reverse();
  const articles = Array.from({ length: 4 }, (_, index) => ({
    news_id: `n${index}`,
    title: `기사 ${index}`,
    press: "언론사",
    article_date: `2026-09-${26 - index}`,
    published_at: `2026-09-${26 - index}T08:00:00+09:00`,
  }));
  const client = new FakeClient({
    news_sentiment_tracks: [{ data: trackRows, error: null }],
    news_sentiment_daily: [{ data: daily, error: null }],
    news_articles: [{ data: articles, error: null }],
  });

  const result = await loadSupabaseSentiment("005930", client as never);

  assert.equal(result.historical?.days.length, 20);
  assert.equal(result.historical?.days[0].date, "2025-11-03");
  assert.equal(result.historical?.days.at(-1)?.date, "2025-11-22");
  assert.deepEqual(result.live, {
    score: 0.45,
    scoreStd: 0.2,
    articleCount: 12,
    publisherCount: 5,
    status: "partial",
    asOf: "2026-09-26T09:00:00+09:00",
    windowStart: "2026-09-25",
    windowEnd: "2026-09-26",
    coverage: {
      fetched_count: 100,
      relevant_count: 12,
      publisher_count: 5,
      newest_published_at: "2026-09-26T08:40:00+09:00",
      lag_minutes: 20,
      provider_total_results: 120,
      provider_returned_count: 100,
      provider_pages: 2,
      provider_truncated: true,
    },
  });
  assert.deepEqual(result.headlines.map(({ title }) => title), ["기사 0", "기사 1", "기사 2"]);
  assert.ok(client.operations.news_sentiment_daily.some(([name, count]) => name === "limit" && count === 20));
  assert.ok(client.operations.news_articles.some(([name, count]) => name === "limit" && count === 3));
});

test("Supabase 재무는 최신 스냅샷과 여섯 지표의 근거를 화면 계약으로 바꾼다", async () => {
  const snapshot = {
    id: "snapshot-id",
    fiscal_year: 2024,
    statement: "CFS",
    receipt_no: "20250311001085",
    filed_at: "2025-03-11",
    shares_basis: "2024-12-31 common_shares",
    price_as_of: "2025-12-30",
  };
  const keys = ["per", "pbr", "roe", "operating_margin", "debt_ratio", "revenue_growth"];
  const metrics = keys.map((metric_key, index) => ({
    metric_key,
    value: index + 1,
    unit: index < 2 ? "multiple" : "percent",
    basis: `${metric_key} 근거`,
    note: null,
  }));
  const client = new FakeClient({
    financial_snapshots: [{ data: snapshot, error: null }],
    financial_metrics: [{ data: metrics, error: null }],
  });

  const result = await loadSupabaseFinancial("005930", client as never);

  assert.match(result?.period ?? "", /2024 사업연도 · 연결재무제표.*2025-03-11 공시/);
  assert.deepEqual(result?.metrics.map(({ key, basis }) => [key, basis]),
    keys.map((key) => [key, `${key} 근거`]));
});

test("Supabase 조회 오류는 호출자에게 전달해 섹션별 폴백을 가능하게 한다", async () => {
  const client = new FakeClient({
    news_sentiment_tracks: [{ data: null, error: { message: "unavailable" } }],
  });

  await assert.rejects(() => loadSupabaseSentiment("005930", client as never), /unavailable/);
});
