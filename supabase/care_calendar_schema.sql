-- Template: scripts/build_care_calendar.py embeds verified reference data.
-- Run generated seed_species_care_calendar.sql in Supabase SQL Editor.
-- This creates independent public care-reference tables. No tree/report updates.
begin;

create table if not exists public.tree_species_care_profiles (
    id uuid primary key default gen_random_uuid(),
    species_name text not null unique check (length(btrim(species_name)) > 0),
    expert_status text not null default 'pending' check (expert_status in ('pending','approved')),
    notes text not null default '全年例行觀察已建檔；樹種專屬月份依來源及臺北現地觀察持續維護。',
    updated_at timestamptz not null default now()
);

create table if not exists public.tree_species_care_rules (
    id uuid primary key,
    species_name text not null references public.tree_species_care_profiles(species_name),
    months integer[] not null check (months <@ array[1,2,3,4,5,6,7,8,9,10,11,12]),
    rule_type text not null check (rule_type in ('general','flower','fruit','assessment')),
    event text not null,
    action text not null,
    source_urls jsonb not null check (jsonb_typeof(source_urls) = 'array' and jsonb_array_length(source_urls) > 0),
    source_note text not null,
    evidence_level text not null check (evidence_level in ('general','reference','conflict','approved')),
    enabled boolean not null default true,
    updated_at timestamptz not null default now(),
    check (not enabled or (cardinality(months) > 0 and evidence_level <> 'conflict'))
);

comment on table public.tree_species_care_profiles is '全樹種養護資料目錄；參考月份不代表已通過現地專業審核。';
comment on table public.tree_species_care_rules is '有來源的物候觀察及養護評估參考；不自動構成修剪施工指令。';

alter table public.tree_species_care_profiles enable row level security;
alter table public.tree_species_care_rules enable row level security;
revoke all on public.tree_species_care_profiles, public.tree_species_care_rules from public, anon, authenticated;
grant select on public.tree_species_care_profiles, public.tree_species_care_rules to anon, authenticated;
do $$
begin
    if not exists (select 1 from pg_policies where schemaname='public' and tablename='tree_species_care_profiles' and policyname='read_care_profiles') then
        create policy read_care_profiles on public.tree_species_care_profiles for select to anon, authenticated using (true);
    end if;
    if not exists (select 1 from pg_policies where schemaname='public' and tablename='tree_species_care_rules' and policyname='read_care_rules') then
        create policy read_care_rules on public.tree_species_care_rules for select to anon, authenticated using (true);
    end if;
end $$;

-- Include ALL live species, including names without species-specific evidence.
insert into public.tree_species_care_profiles (species_name)
select distinct btrim(species_name) from public.tree_locations
where species_name is not null and length(btrim(species_name)) > 0
on conflict (species_name) do nothing;

-- All-year baseline indexes ordinary observations, not a legal monthly frequency.
insert into public.tree_species_care_rules (
    id,species_name,months,rule_type,event,action,source_urls,source_note,evidence_level,enabled
)
select md5('kootree-care-general:' || species_name)::uuid, species_name,
       array[1,2,3,4,5,6,7,8,9,10,11,12], 'general', '全年例行觀察',
       '依管理計畫巡查樹冠、枝幹、根際與通行空間，記錄異常後交管理單位評估。',
       '["https://laws.gov.taipei/law/LawSearch/LawArticleContent/FL004003"]'::jsonb,
       '自治條例第4條為巡查依據；全年月份僅作排程索引，非規定每月一次，亦非樹種專屬物候或修剪月份。',
       'general', true
from public.tree_species_care_profiles
on conflict (id) do nothing;

with seed as (
    select * from jsonb_to_recordset($care_seed$
-- CARE_SEEDS_JSON
$care_seed$::jsonb) as item (
        species_key text, months integer[], rule_type text, event text, action text,
        source_urls jsonb, source_note text, evidence_level text, enabled boolean
    )
)
insert into public.tree_species_care_rules (
    id,species_name,months,rule_type,event,action,source_urls,source_note,evidence_level,enabled
)
select md5('kootree-care-reference:' || profile.species_name || ':' || seed.rule_type || ':' || seed.source_urls::text)::uuid,
       profile.species_name,seed.months,seed.rule_type,seed.event,seed.action,
       seed.source_urls,seed.source_note,seed.evidence_level,seed.enabled
from public.tree_species_care_profiles profile
join seed on replace(regexp_replace(profile.species_name, '\s', '', 'g'), '臺', '台') = seed.species_key
-- Preserve existing records and any expert edits; rerunning only adds missing rows.
on conflict (id) do nothing;

do $$
begin
    if exists (
        select 1 from public.tree_locations tree where tree.species_name is not null
        and length(btrim(tree.species_name)) > 0
        and not exists (select 1 from public.tree_species_care_profiles profile
                        where profile.species_name = btrim(tree.species_name))
    ) then
        raise exception '樹種目錄覆蓋不完整，交易回滾。';
    end if;
end $$;

commit;

select (select count(*) from public.tree_species_care_profiles) as species_profiles,
       count(*) filter (where rule_type='general' and enabled) as general_rules,
       count(*) filter (where rule_type<>'general' and enabled) as enabled_reference_rules,
       count(*) filter (where evidence_level='conflict') as conflict_rules
from public.tree_species_care_rules;
