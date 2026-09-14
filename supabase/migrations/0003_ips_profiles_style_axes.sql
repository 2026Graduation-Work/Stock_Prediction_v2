-- 미적용 — 적용 전 담당자 확인 필요.
-- profiling_output schema v1.1: ips_profiles에 8축(style_axes)을 저장한다.
-- 기존 행은 schema_version '1.0.0', style_axes null 그대로 둔다.
alter table public.ips_profiles
  drop constraint if exists ips_profiles_schema_version_check;
alter table public.ips_profiles
  add constraint ips_profiles_schema_version_check
  check (schema_version in ('1.0.0', '1.1.0'));

alter table public.ips_profiles
  add column if not exists style_axes jsonb;
