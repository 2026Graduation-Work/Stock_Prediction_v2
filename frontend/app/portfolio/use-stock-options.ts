"use client";

import { useEffect, useState } from "react";
import { getSupabaseClient } from "@/lib/supabase";

export type StockOption = { code: string; name: string };

// 종목 후보. 데모는 고정 목록, 로그인 사용자는 종목 마스터가 크므로 입력한 만큼만 검색한다.
export function useStockOptions(keyword: string, supabaseMode: boolean, catalog: StockOption[]) {
  const [options, setOptions] = useState(catalog);

  useEffect(() => {
    if (!supabaseMode) return;
    const trimmed = keyword.trim();
    if (trimmed.length < 1) return;
    const client = getSupabaseClient();
    if (!client) return;

    let active = true;
    const timer = setTimeout(() => {
      void client
        .from("stocks")
        .select("code,name")
        .or(`name.ilike.%${trimmed}%,code.ilike.${trimmed}%`)
        .limit(20)
        .then(({ data }) => {
          if (active && data) setOptions(data as StockOption[]);
        });
    }, 250);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [keyword, supabaseMode]);

  // 입력값과 정확히 맞는 후보(이름 또는 코드)
  const match = options.find((item) => item.name === keyword.trim() || item.code === keyword.trim());
  return { options, match };
}
