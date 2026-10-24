-- Kootree dashboard simulation: run in this project's Supabase SQL Editor.
-- Creates ONLY dashboard_demo_reports; never modifies tree_reports or tree_locations.
-- Requires a role that can create tables/policies. A publishable API key cannot run DDL.
-- Every row is explicitly synthetic. Do not use these scores for real tree decisions.
begin;

create table if not exists public.dashboard_demo_reports (
    id uuid primary key,
    tree_location_id uuid not null references public.tree_locations(id),
    type text not null,
    photos jsonb not null default '[]'::jsonb check (photos = '[]'::jsonb),
    note text not null check (note like '【模擬資料】%'),
    created_at timestamptz not null,
    confirmed_at timestamptz,
    dismissed boolean not null default false,
    is_simulated boolean not null default true check (is_simulated = true),
    simulation_batch text not null,
    source_report_id uuid not null,
    risk_score integer not null check (risk_score between 0 and 100),
    risk_level text generated always as (
        case when risk_score >= 70 then '高'
             when risk_score >= 40 then '中' else '低' end
    ) stored,
    check (confirmed_at is null or confirmed_at >= created_at),
    check (not dismissed or confirmed_at is null)
);

comment on table public.dashboard_demo_reports is
    'Kootree 虛構展示通報及風險分數；與真實市民案件分開，不可作為樹木安全診斷或養護指令。';
comment on column public.dashboard_demo_reports.source_report_id is
    '僅記錄欄位原型的來源編號；未複製來源使用者、照片、位置或通報文字。';

alter table public.dashboard_demo_reports enable row level security;
revoke all on public.dashboard_demo_reports from public, anon, authenticated;
grant select on public.dashboard_demo_reports to anon, authenticated;

do $$
begin
    if not exists (
        select 1 from pg_policies where schemaname = 'public'
        and tablename = 'dashboard_demo_reports' and policyname = 'read_dashboard_simulations'
    ) then
        create policy read_dashboard_simulations on public.dashboard_demo_reports
            for select to anon, authenticated using (is_simulated = true);
    end if;
    if not exists (select 1 from public.tree_reports) then
        raise exception '尚無真實通報可作為欄位原型，停止產生模擬資料。';
    end if;
    if (select count(*) from public.tree_locations where tree_type = 'street') < 200 then
        raise exception '行道樹不足 200 筆，停止產生模擬資料。';
    end if;
end $$;

-- Balanced selection across the districts present in the live street tree table.
-- Batch and UUIDs are deterministic: rerunning this file does not duplicate rows.
with prototype as (
    select id, coalesce(nullif(type::text, ''), '其他') as type
    from public.tree_reports order by created_at, id limit 1
), ranked as (
    select id, division_name,
           row_number() over (
               partition by division_name
               order by md5(id::text || 'kootree-demo-20261024'), id
           ) as district_rank
    from public.tree_locations where tree_type = 'street'
), chosen as (
    select id, row_number() over (order by district_rank, division_name nulls last, id) as n
    from ranked order by district_rank, division_name nulls last, id limit 200
), payload as (
    select chosen.*, prototype.id as source_id,
        (array[prototype.type, '落枝枯枝', '側枝遮擋', '根系隆起', '病蟲害', '落果飛絮', '樹木傾斜'])
            [1 + ((n - 1) % 7)::integer] as issue_type,
        current_timestamp - (1 + ((n - 1) % 21)) * interval '1 day' as reported_at
    from chosen cross join prototype
)
insert into public.dashboard_demo_reports (
    id, tree_location_id, type, note, created_at, confirmed_at, dismissed,
    is_simulated, simulation_batch, source_report_id, risk_score
)
select md5('kootree-demo-20261024:' || n::text)::uuid, id, issue_type,
       '【模擬資料】展示用通報：' || issue_type || '。非市民實際陳情；風險分數為虛構。',
       reported_at,
       case when n % 5 in (1, 2) then reported_at + interval '12 hours' else null end,
       n % 5 = 0,
       true, 'kootree-demo-20261024', source_id,
       (20 + (n * 17) % 70)::integer
from payload
on conflict (id) do nothing;

do $$
begin
    if (select count(*) from public.dashboard_demo_reports
        where simulation_batch = 'kootree-demo-20261024' and is_simulated) <> 200 then
        raise exception '模擬批次驗證失敗：預期 200 筆，所有變更將回滾。';
    end if;
end $$;

commit;

-- Result: 200 reports; 80 pending confirmation, 80 confirmed, 40 dismissed.
select simulation_batch, count(*) as simulated_reports,
       count(*) filter (where not dismissed and confirmed_at is null) as pending_confirmation,
       count(*) filter (where not dismissed and confirmed_at is not null) as confirmed,
       count(*) filter (where dismissed) as dismissed
from public.dashboard_demo_reports
where simulation_batch = 'kootree-demo-20261024'
group by simulation_batch;
