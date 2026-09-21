// 보유 종목 입력 규칙. I/O(save-holdings.ts)와 분리해 두어 단위 테스트에서 바로 쓴다.

export interface SavedHolding {
  code: string;
  name: string;
  quantity: number;
  avgBuyPrice: number;
}

// 수량 0은 "보유 안 함"이라 저장하지 않는다. 평단 0은 허용한다(무상증자 등).
export function isValidHolding(value: SavedHolding): boolean {
  return (
    /^\d{6}$/.test(value.code) &&
    value.name.trim().length > 0 &&
    Number.isInteger(value.quantity) &&
    value.quantity > 0 &&
    Number.isInteger(value.avgBuyPrice) &&
    value.avgBuyPrice >= 0
  );
}

// null = 저장한 적 없음, [] = 전부 지웠음. 둘을 구분해야 데모 시드를 되살릴지 판단할 수 있다.
export function parseSavedHoldings(serialized: string | null): SavedHolding[] | null {
  if (!serialized) return null;
  try {
    const parsed: unknown = JSON.parse(serialized);
    if (!Array.isArray(parsed)) return null;
    return parsed.filter(
      (item): item is SavedHolding =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as SavedHolding).code === "string" &&
        typeof (item as SavedHolding).name === "string" &&
        typeof (item as SavedHolding).quantity === "number" &&
        typeof (item as SavedHolding).avgBuyPrice === "number",
    );
  } catch {
    return null;
  }
}
