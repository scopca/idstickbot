-- Supabase setup for idstickbot — run in Supabase SQL Editor
-- Table for per-user language preferences (EN / RU / UZ)
-- Free tier: 500 MB is more than enough ( ~50 bytes per user)

create table if not exists public.user_langs (
  user_id bigint primary key,
  lang text not null check (lang in ('en','ru','uz')),
  updated_at timestamptz default now()
);

-- Enable Row Level Security (required for Data API)
alter table public.user_langs enable row level security;

-- Policies: allow anon & authenticated to read/insert/update their own row
-- For a bot backend you can also use the service_role key (bypasses RLS),
-- but these policies make anon key work for simplicity.

drop policy if exists "Allow all read" on public.user_langs;
create policy "Allow all read" on public.user_langs
  for select using (true);

drop policy if exists "Allow all insert" on public.user_langs;
create policy "Allow all insert" on public.user_langs
  for insert with check (true);

drop policy if exists "Allow all update" on public.user_langs;
create policy "Allow all update" on public.user_langs
  for update using (true) with check (true);

-- Optional: also allow delete (not used)
drop policy if exists "Allow all delete" on public.user_langs;
create policy "Allow all delete" on public.user_langs
  for delete using (true);

-- Grant API access (Data API)
grant select, insert, update, delete on public.user_langs to anon;
grant select, insert, update, delete on public.user_langs to authenticated;
grant all on public.user_langs to service_role;

-- Optional: expose via Data API (if not using default privileges)
-- In Supabase Dashboard: Settings → Data API → Expose public.user_langs = true

-- Example: check table
-- select * from public.user_langs limit 10;
