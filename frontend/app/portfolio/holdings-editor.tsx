"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import DisclaimerFooter from "../components/disclaimer-footer";
import SiteHeader from "../components/site-header";
import { useOnboarding } from "../components/onboarding-provider";
import { getSupabaseClient } from "@/lib/supabase";
import {
  getSavedHoldingsSnapshot,
  getServerHoldingsSnapshot,
  isValidHolding,
  parseSavedHoldings,
  saveHoldings,
  subscribeToSavedHoldings,
  type SavedHolding,
} from "@/lib/save-holdings";
import type { InvestorProfileSummary, MarketStatus, PortfolioHolding } from "@/lib/types";

interface HoldingsEditorProps {
  profile: InvestorProfileSummary;
  marketStatus: MarketStatus;
  catalog: { code: string; name: string }[];
  demoHoldings: PortfolioHolding[];
}

type Draft = { code: string; name: string; quantity: string; avgBuyPrice: string };

const EMPTY_DRAFT: Draft = { code: "", name: "", quantity: "", avgBuyPrice: "" };

function toInt(value: string): number {
  const parsed = Number.parseInt(value.replaceAll(",", "").trim(), 10);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function formatWon(value: number): string {
  return value.toLocaleString("ko-KR");
}

export default function HoldingsEditor({
  profile,
  marketStatus,
  catalog,
  demoHoldings,
}: HoldingsEditorProps) {
  const { state: onboardingState } = useOnboarding();
  const supabaseMode = onboardingState.mode === "supabase";

  const savedSnapshot = useSyncExternalStore(
    subscribeToSavedHoldings,
    getSavedHoldingsSnapshot,
    getServerHoldingsSnapshot,
  );
  const saved = parseSavedHoldings(savedSnapshot);

  // 저장된 목록이 있으면 그것이 정답이다. 없을 때만 데모 시드를 보여 준다.
  // (로그인 사용자는 데모 시드를 받지 않으므로 빈 목록에서 시작한다.)
  const initial: SavedHolding[] =
    saved ??
    (supabaseMode
      ? []
      : demoHoldings.map(({ code, name, quantity, avgBuyPrice }) => ({
          code,
          name,
          quantity,
          avgBuyPrice,
        })));

  const [rows, setRows] = useState<SavedHolding[]>(initial);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [options, setOptions] = useState(catalog);
  const [status, setStatus] = useState<"idle" | "saving" | "saved">("idle");
  const [error, setError] = useState("");

  // 로그인 사용자는 종목 마스터가 크므로 입력한 만큼만 검색한다.
  useEffect(() => {
    if (!supabaseMode) return;
    const keyword = draft.name.trim();
    if (keyword.length < 1) return;
    const client = getSupabaseClient();
    if (!client) return;

    let active = true;
    const timer = setTimeout(() => {
      void client
        .from("stocks")
        .select("code,name")
        .or(`name.ilike.%${keyword}%,code.ilike.${keyword}%`)
        .limit(20)
        .then(({ data }) => {
          if (active && data) setOptions(data as { code: string; name: string }[]);
        });
    }, 250);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [draft.name, supabaseMode]);

  function addRow() {
    setError("");
    const match = options.find(
      (item) => item.name === draft.name.trim() || item.code === draft.name.trim(),
    );
    const code = match?.code ?? draft.code.trim();
    const name = match?.name ?? draft.name.trim();
    const candidate: SavedHolding = {
      code,
      name,
      quantity: toInt(draft.quantity),
      avgBuyPrice: toInt(draft.avgBuyPrice),
    };

    if (!match) {
      setError("목록에 있는 종목을 골라 주세요. 종목명을 입력하면 후보가 나옵니다.");
      return;
    }
    if (rows.some((row) => row.code === candidate.code)) {
      setError(`${name}은(는) 이미 목록에 있습니다. 아래에서 수량을 고쳐 주세요.`);
      return;
    }
    if (!isValidHolding(candidate)) {
      setError("수량은 1 이상, 평균 매입가는 0 이상의 정수로 입력해 주세요.");
      return;
    }

    setRows((current) => [...current, candidate]);
    setDraft(EMPTY_DRAFT);
    setStatus("idle");
  }

  function updateRow(code: string, patch: Partial<SavedHolding>) {
    setRows((current) =>
      current.map((row) => (row.code === code ? { ...row, ...patch } : row)),
    );
    setStatus("idle");
  }

  function removeRow(code: string) {
    setRows((current) => current.filter((row) => row.code !== code));
    setStatus("idle");
  }

  async function submit() {
    setError("");
    setStatus("saving");
    try {
      await saveHoldings(rows, onboardingState.mode === "supabase" ? "supabase" : "demo");
      setStatus("saved");
    } catch (cause) {
      setStatus("idle");
      setError(cause instanceof Error ? cause.message : "저장하지 못했습니다.");
    }
  }

  const total = rows.reduce((sum, row) => sum + row.quantity * row.avgBuyPrice, 0);

  return (
    <div className="w-full">
      <SiteHeader
        profile={profile}
        marketStatus={marketStatus}
        activePage="portfolio"
      />

      <div className="mx-auto box-border flex w-full max-w-[880px] flex-col gap-6 px-5 pt-6 sm:px-8">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-xl font-semibold">보유 종목</h1>
          <p className="text-sm text-body">
            직접 입력한 수량과 평균 매입가로 포트폴리오 맵과 보유 종목 알림을 만듭니다.
            증권사 계좌를 연동하지 않으며, 입력한 값은 매매에 쓰이지 않습니다.
          </p>
        </div>

        {/* 추가 폼 */}
        <section className="flex flex-col gap-3 rounded-lg border border-line bg-white px-5 py-5">
          <h2 className="text-sm font-semibold">종목 추가</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1.4fr_0.8fr_1fr_max-content]">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-muted">종목명 또는 코드</span>
              <input
                list="stock-catalog"
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                placeholder="삼성전자"
                className="h-10 rounded-md border border-edge bg-field px-3 text-sm outline-none placeholder:text-faint focus:border-brand focus:bg-white"
              />
              <datalist id="stock-catalog">
                {options.map((item) => (
                  <option key={item.code} value={item.name}>
                    {item.code}
                  </option>
                ))}
              </datalist>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-muted">수량 (주)</span>
              <input
                inputMode="numeric"
                value={draft.quantity}
                onChange={(event) => setDraft({ ...draft, quantity: event.target.value })}
                placeholder="10"
                className="h-10 rounded-md border border-edge bg-field px-3 text-sm tabular-nums outline-none placeholder:text-faint focus:border-brand focus:bg-white"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-muted">평균 매입가 (원)</span>
              <input
                inputMode="numeric"
                value={draft.avgBuyPrice}
                onChange={(event) => setDraft({ ...draft, avgBuyPrice: event.target.value })}
                placeholder="71,200"
                className="h-10 rounded-md border border-edge bg-field px-3 text-sm tabular-nums outline-none placeholder:text-faint focus:border-brand focus:bg-white"
              />
            </label>
            <button
              type="button"
              onClick={addRow}
              className="h-10 self-end whitespace-nowrap rounded-md bg-ink px-5 text-sm font-medium text-white hover:bg-body"
            >
              추가
            </button>
          </div>
          {error && (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          )}
        </section>

        {/* 목록 */}
        <section className="flex flex-col gap-3 rounded-lg border border-line bg-white px-5 py-5">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="text-sm font-semibold">
              등록한 종목 <span className="text-muted tabular-nums">{rows.length}개</span>
            </h2>
            {rows.length > 0 && (
              <span className="text-xs text-muted tabular-nums">
                등록 매입금액 합계 {formatWon(total)}원
              </span>
            )}
          </div>

          {rows.length === 0 ? (
            <div className="rounded-md bg-field px-4 py-8 text-center">
              <p className="text-sm font-medium">아직 등록한 종목이 없습니다</p>
              <p className="mt-1.5 text-xs text-muted">
                위에서 종목을 추가하면 대시보드에 포트폴리오 맵과 보유 종목 알림이 나타납니다.
              </p>
            </div>
          ) : (
            <ul className="flex flex-col">
              {rows.map((row) => (
                <li
                  key={row.code}
                  className="grid grid-cols-1 items-center gap-3 border-t border-line-soft py-3 first:border-t-0 sm:grid-cols-[1.4fr_0.8fr_1fr_auto]"
                >
                  <div className="flex flex-col">
                    <span className="text-sm font-medium">{row.name}</span>
                    <span className="text-xs text-faint tabular-nums">{row.code}</span>
                  </div>
                  <label className="flex items-center gap-2">
                    <span className="text-xs text-muted sm:hidden">수량</span>
                    <input
                      inputMode="numeric"
                      aria-label={`${row.name} 수량`}
                      value={String(row.quantity)}
                      onChange={(event) =>
                        updateRow(row.code, { quantity: toInt(event.target.value) })
                      }
                      className="h-9 w-full rounded-md border border-edge bg-field px-3 text-sm tabular-nums outline-none focus:border-brand focus:bg-white"
                    />
                  </label>
                  <label className="flex items-center gap-2">
                    <span className="text-xs text-muted sm:hidden">평단</span>
                    <input
                      inputMode="numeric"
                      aria-label={`${row.name} 평균 매입가`}
                      value={String(row.avgBuyPrice)}
                      onChange={(event) =>
                        updateRow(row.code, { avgBuyPrice: toInt(event.target.value) })
                      }
                      className="h-9 w-full rounded-md border border-edge bg-field px-3 text-sm tabular-nums outline-none focus:border-brand focus:bg-white"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => removeRow(row.code)}
                    className="h-9 justify-self-start rounded-md border border-edge px-3 text-xs font-medium text-muted hover:border-ghost hover:text-ink sm:justify-self-end"
                  >
                    삭제
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={submit}
            disabled={status === "saving"}
            className="h-10 rounded-md bg-brand px-6 text-sm font-medium text-white hover:bg-brand-deep disabled:opacity-60"
          >
            {status === "saving" ? "저장 중…" : "저장"}
          </button>
          {status === "saved" && (
            <span role="status" className="text-sm text-body">
              저장했습니다.{" "}
              <Link href="/">대시보드에서 확인하기 →</Link>
            </span>
          )}
          <span className="ml-auto text-xs text-faint">
            {supabaseMode
              ? "내 계정에 저장됩니다"
              : "데모 계정이라 이 브라우저에만 저장됩니다"}
          </span>
        </div>
      </div>

      <DisclaimerFooter fixed={false} />
    </div>
  );
}
