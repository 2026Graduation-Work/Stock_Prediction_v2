import type { Page, Route } from "@playwright/test";

// e2e 서버는 NEXT_PUBLIC_SUPABASE_URL을 이 주소로 띄운다(playwright.config.ts, web-ci.yml).
// 실제 Supabase 없이 브라우저가 부르는 Auth·REST 요청만 가로채 흉내 낸다. 서버 쪽 조회는 연결 실패 → 정적 폴백.
export const SUPABASE_URL = "http://127.0.0.1:54321";

interface MockUser {
  id: string;
  email: string;
  password: string;
}

function session(user: MockUser) {
  const now = Math.floor(Date.now() / 1000);
  return {
    access_token: `access-${user.id}`,
    refresh_token: `refresh-${user.id}`,
    token_type: "bearer",
    expires_in: 3600,
    expires_at: now + 3600,
    user: authUser(user),
  };
}

function authUser(user: MockUser) {
  return {
    id: user.id,
    aud: "authenticated",
    role: "authenticated",
    email: user.email,
    app_metadata: { provider: "email" },
    user_metadata: {},
    created_at: new Date().toISOString(),
  };
}

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

// 가입·로그인·로그아웃만 흉내 낸다. 서비스 사용자(users)·성향(ips_profiles)은 없음 → 설문 필요 상태.
export async function mockSupabaseAuth(page: Page) {
  const users = new Map<string, MockUser>();
  let current: MockUser | null = null;
  const calls: string[] = [];

  await page.route(`${SUPABASE_URL}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    calls.push(`${request.method()} ${url.pathname}`);
    if (url.pathname === "/auth/v1/signup") {
      const { email, password } = request.postDataJSON() as { email: string; password: string };
      const user = { id: `user-${users.size + 1}`, email, password };
      users.set(email, user);
      current = user;
      return json(route, session(user));
    }
    if (url.pathname === "/auth/v1/token" && url.searchParams.get("grant_type") === "password") {
      const { email, password } = request.postDataJSON() as { email: string; password: string };
      const user = users.get(email);
      if (!user || user.password !== password) {
        return json(route, { error: "invalid_grant", error_description: "Invalid login credentials" }, 400);
      }
      current = user;
      return json(route, session(user));
    }
    if (url.pathname === "/auth/v1/user") {
      return current ? json(route, authUser(current)) : json(route, { message: "no user" }, 401);
    }
    if (url.pathname === "/auth/v1/logout") {
      current = null;
      return route.fulfill({ status: 204 });
    }
    if (url.pathname.startsWith("/rest/v1/")) return json(route, request.method() === "GET" ? [] : {});
    return json(route, {});
  });
  return { calls };
}
