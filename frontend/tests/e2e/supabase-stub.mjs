// e2e용 빈 Supabase: 서버 렌더링이 부르는 REST 조회에 빈 결과를 바로 돌려준다(연결 실패 재시도로 느려지지 않게).
// 브라우저 쪽 Auth 흐름은 각 테스트가 page.route로 따로 흉내 낸다(supabase-mock.ts).
import { createServer } from "node:http";

createServer((request, response) => {
  const rest = request.url?.startsWith("/rest/v1/");
  response.writeHead(rest ? 200 : 404, { "Content-Type": "application/json" });
  response.end(rest && request.method === "GET" ? "[]" : "{}");
}).listen(54321, "127.0.0.1");
