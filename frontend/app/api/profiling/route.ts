// SSOT는 backend/profiling/입니다. 규칙 변경 시 Python 상수 테이블과 동기화합니다.

import { NextResponse } from "next/server";
import { convertSurveyAnswers } from "@/lib/profiling-rules";

export async function POST(request: Request) {
  try {
    const answers: unknown = await request.json();
    return NextResponse.json(convertSurveyAnswers(answers));
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "설문 응답을 변환하지 못했습니다.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
