-- Add the compact market ticker payload used by the shared application header.
alter table public.market_status
  add column if not exists index_quotes jsonb not null default '[]'::jsonb;
