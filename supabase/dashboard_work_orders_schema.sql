-- Optional maintenance work-order source. Does not create simulated jobs.
begin;
create table if not exists public.dashboard_work_orders (
 id uuid primary key default gen_random_uuid(),
 tree_location_id uuid not null references public.tree_locations(id),
 report_id uuid,
 job_status text not null check(job_status in ('待派工','處理中','已完成','已取消')),
 action text not null,
 team text,
 created_at timestamptz not null default now(),
 inspection_at timestamptz,
 completed_at timestamptz,
 is_simulated boolean not null default false,
 check(completed_at is null or completed_at>=created_at),
 check(job_status<>'已完成' or completed_at is not null)
);
alter table public.dashboard_work_orders enable row level security;
revoke all on public.dashboard_work_orders from public, anon, authenticated;
grant select on public.dashboard_work_orders to anon, authenticated;
do $$ begin
 if not exists(select 1 from pg_policies where schemaname='public' and tablename='dashboard_work_orders' and policyname='read_dashboard_work_orders') then
  create policy read_dashboard_work_orders on public.dashboard_work_orders for select to anon, authenticated using (true);
 end if;
end $$;
commit;
