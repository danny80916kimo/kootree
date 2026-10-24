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
[
  {
    "species_key": "九芎",
    "months": [
      6,
      7,
      8
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/537d727947db486b9412642bc677fe71"
    ],
    "source_note": "林業及自然保育署記載：6~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "九芎",
    "months": [
      9,
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/537d727947db486b9412642bc677fe71"
    ],
    "source_note": "林業及自然保育署記載：9~12月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "光蠟樹",
    "months": [
      6,
      7
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/1c2630f7740e43949e93f57ce61ba2b3"
    ],
    "source_note": "林業及自然保育署記載：6~7月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "光蠟樹",
    "months": [
      7,
      8,
      9,
      10
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/1c2630f7740e43949e93f57ce61ba2b3"
    ],
    "source_note": "林業及自然保育署記載：7~10月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "厚皮香",
    "months": [
      5,
      6
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/df4ccb3015654d8daab736607466f3b6"
    ],
    "source_note": "林業及自然保育署記載：5~6月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "厚皮香",
    "months": [
      8,
      9,
      10
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/df4ccb3015654d8daab736607466f3b6"
    ],
    "source_note": "林業及自然保育署記載：8~10月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "厚葉石斑木",
    "months": [
      2,
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/f6bb352bf8bc4f7fb42b3578f806dafb"
    ],
    "source_note": "林業及自然保育署記載：2~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "厚葉石斑木",
    "months": [
      8,
      9,
      10,
      11
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/f6bb352bf8bc4f7fb42b3578f806dafb"
    ],
    "source_note": "林業及自然保育署記載：8~11月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "土肉桂",
    "months": [
      3,
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/d8fb35b56aa943298b7e279b2ecee55c"
    ],
    "source_note": "林業及自然保育署記載：3~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "土肉桂",
    "months": [
      9,
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/d8fb35b56aa943298b7e279b2ecee55c"
    ],
    "source_note": "林業及自然保育署記載：9~12月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "大葉山欖",
    "months": [
      1,
      11,
      12
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/78ba1aac49f24f8eba93142eef4fb626"
    ],
    "source_note": "林業及自然保育署記載：11~1月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "大葉山欖",
    "months": [
      7,
      8
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/78ba1aac49f24f8eba93142eef4fb626"
    ],
    "source_note": "林業及自然保育署記載：7~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "大葉楠",
    "months": [
      2,
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/85873795a7434bfa803ba0913aef2da9"
    ],
    "source_note": "林業及自然保育署記載：2~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "大葉楠",
    "months": [
      7,
      8,
      9,
      10,
      11
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/85873795a7434bfa803ba0913aef2da9"
    ],
    "source_note": "林業及自然保育署記載：7~11月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "大葉羅漢松",
    "months": [
      5,
      6,
      7
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/e658e2cf0dbb47e0b10b183ca27da5e4"
    ],
    "source_note": "林業及自然保育署記載：5~7月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "大葉羅漢松",
    "months": [
      8,
      9
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/e658e2cf0dbb47e0b10b183ca27da5e4"
    ],
    "source_note": "林業及自然保育署記載：8~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "小葉羅漢松",
    "months": [
      3,
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/129c005ff2de49619abf7aa0e3c7b5bf"
    ],
    "source_note": "林業及自然保育署記載：3~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "小葉羅漢松",
    "months": [
      8,
      9
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/129c005ff2de49619abf7aa0e3c7b5bf"
    ],
    "source_note": "林業及自然保育署記載：8~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "山櫻花",
    "months": [
      1,
      2,
      3
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/461cb462f46349aea4fb6b6c9de1bb5b"
    ],
    "source_note": "林業及自然保育署記載：1~3月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "山櫻花",
    "months": [
      6,
      7
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/461cb462f46349aea4fb6b6c9de1bb5b"
    ],
    "source_note": "林業及自然保育署記載：6~7月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "山菜豆",
    "months": [
      5,
      6,
      7,
      8,
      9
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/58058d7acfe24ae9be24f39eb3e2d204"
    ],
    "source_note": "林業及自然保育署記載：5~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "山菜豆",
    "months": [
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/58058d7acfe24ae9be24f39eb3e2d204"
    ],
    "source_note": "林業及自然保育署記載：10~12月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "月橘",
    "months": [
      7,
      8,
      9
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/d8e855416820488ab8da3b6909262bd7"
    ],
    "source_note": "林業及自然保育署記載：7~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "月橘",
    "months": [
      9,
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/d8e855416820488ab8da3b6909262bd7"
    ],
    "source_note": "林業及自然保育署記載：9~12月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "朴樹",
    "months": [
      1,
      2,
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/5a7f7791d1e64bb68a9a11eb44926284"
    ],
    "source_note": "林業及自然保育署記載：1~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "朴樹",
    "months": [
      8,
      9
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/5a7f7791d1e64bb68a9a11eb44926284"
    ],
    "source_note": "林業及自然保育署記載：8~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "杜英",
    "months": [
      5,
      6,
      7,
      8
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/7ccade3c-bd10-403d-8b40-75dda9f5dab9"
    ],
    "source_note": "林業及自然保育署記載：5~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "杜英",
    "months": [
      8,
      9,
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/7ccade3c-bd10-403d-8b40-75dda9f5dab9"
    ],
    "source_note": "林業及自然保育署記載：8~12月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "森氏紅淡比",
    "months": [
      1,
      2,
      3,
      4,
      5,
      6
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/acfdfe484d6d4b148f25c99f8274736a"
    ],
    "source_note": "林業及自然保育署記載：1~6月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "森氏紅淡比",
    "months": [
      7,
      8,
      9
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/acfdfe484d6d4b148f25c99f8274736a"
    ],
    "source_note": "林業及自然保育署記載：7~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "楊梅",
    "months": [
      3,
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/43673b9cb92248fdb7c360287b2918e8"
    ],
    "source_note": "林業及自然保育署記載：3~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "楊梅",
    "months": [
      5,
      6,
      7,
      8
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/43673b9cb92248fdb7c360287b2918e8"
    ],
    "source_note": "林業及自然保育署記載：5~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "楓香",
    "months": [
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/2d3f9adf863f426d94a2fad294582e4c"
    ],
    "source_note": "林業及自然保育署記載：4~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "楓香",
    "months": [
      10,
      11
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/2d3f9adf863f426d94a2fad294582e4c"
    ],
    "source_note": "林業及自然保育署記載：10~11月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "榔榆",
    "months": [
      9,
      10
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/46c6758b5f434576b90b05c447724dfe"
    ],
    "source_note": "林業及自然保育署記載：9~10月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "榔榆",
    "months": [
      1,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/46c6758b5f434576b90b05c447724dfe"
    ],
    "source_note": "林業及自然保育署記載：11~1月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "樟樹",
    "months": [
      2,
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/ba6879a26e3e45ae8bdee46960f59719"
    ],
    "source_note": "林業及自然保育署記載：2~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "樟樹",
    "months": [
      9,
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/ba6879a26e3e45ae8bdee46960f59719"
    ],
    "source_note": "林業及自然保育署記載：9~12月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "樹杞",
    "months": [
      3,
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/b76064ba550b47adb47d021f6155674c"
    ],
    "source_note": "林業及自然保育署記載：3~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "樹杞",
    "months": [
      2,
      3,
      4
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/b76064ba550b47adb47d021f6155674c"
    ],
    "source_note": "林業及自然保育署記載：2~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "櫸",
    "months": [
      2,
      3
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/de28c1b7f04a41b284b83cb178e4f1fb"
    ],
    "source_note": "林業及自然保育署記載：2~3月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "櫸",
    "months": [
      10,
      11
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/de28c1b7f04a41b284b83cb178e4f1fb"
    ],
    "source_note": "林業及自然保育署記載：10~11月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "欖仁樹",
    "months": [
      4,
      5,
      6,
      7,
      8,
      9
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/895d8e80b81e468ca81f1016f904a3df"
    ],
    "source_note": "林業及自然保育署記載：4~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "欖仁樹",
    "months": [
      9,
      10
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/895d8e80b81e468ca81f1016f904a3df"
    ],
    "source_note": "林業及自然保育署記載：9~10月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "水黃皮",
    "months": [
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/b3d077e216fb4a76888f3e7ca642bb5a"
    ],
    "source_note": "林業及自然保育署記載：4~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "水黃皮",
    "months": [
      6,
      7,
      8
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/b3d077e216fb4a76888f3e7ca642bb5a"
    ],
    "source_note": "林業及自然保育署記載：6~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "江某",
    "months": [
      10,
      11,
      12
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/562d51d3299343a5bff8308690552cbc"
    ],
    "source_note": "林業及自然保育署記載：10~12月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "江某",
    "months": [
      3,
      4,
      5
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/562d51d3299343a5bff8308690552cbc"
    ],
    "source_note": "林業及自然保育署記載：3~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "海桐",
    "months": [
      6,
      7,
      8
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/284e79cce7f647c79ba96ffdad1a787d"
    ],
    "source_note": "林業及自然保育署記載：6~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "海桐",
    "months": [
      9,
      10
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/284e79cce7f647c79ba96ffdad1a787d"
    ],
    "source_note": "林業及自然保育署記載：9~10月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "烏心石",
    "months": [
      11,
      12
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/0a3ae7102cf24a86bcc4f4c06533a6a2"
    ],
    "source_note": "林業及自然保育署記載：11~12月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "烏心石",
    "months": [
      5,
      6,
      7
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/0a3ae7102cf24a86bcc4f4c06533a6a2"
    ],
    "source_note": "林業及自然保育署記載：5~7月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "無患子",
    "months": [
      6,
      7,
      8
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/f8a99837f67c44319c905a93827ce405"
    ],
    "source_note": "林業及自然保育署記載：6~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "無患子",
    "months": [
      8,
      9,
      10,
      11
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/f8a99837f67c44319c905a93827ce405"
    ],
    "source_note": "林業及自然保育署記載：8~11月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "牛樟",
    "months": [
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/9ee2167d0c7c4f09adcb3528fc19e733"
    ],
    "source_note": "林業及自然保育署記載：4~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "牛樟",
    "months": [
      7,
      8
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/9ee2167d0c7c4f09adcb3528fc19e733"
    ],
    "source_note": "林業及自然保育署記載：7~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "珊瑚樹",
    "months": [
      2,
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/325cac4f0e1b4f71b6df5fcc8b45a81a"
    ],
    "source_note": "林業及自然保育署記載：2~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "珊瑚樹",
    "months": [
      4,
      5,
      6,
      7
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/325cac4f0e1b4f71b6df5fcc8b45a81a"
    ],
    "source_note": "林業及自然保育署記載：4~7月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "瓊崖海棠",
    "months": [
      5,
      6
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/c6ea882359824adbb36865b1755a05b7"
    ],
    "source_note": "林業及自然保育署記載：5~6月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "瓊崖海棠",
    "months": [
      10,
      11
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/c6ea882359824adbb36865b1755a05b7"
    ],
    "source_note": "林業及自然保育署記載：10~11月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "相思樹",
    "months": [
      5,
      6,
      7
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/8f667e405ff24303b4c0c52f20216374"
    ],
    "source_note": "林業及自然保育署記載：5~7月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "相思樹",
    "months": [
      7,
      8,
      9
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/8f667e405ff24303b4c0c52f20216374"
    ],
    "source_note": "林業及自然保育署記載：7~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "穗花棋盤腳",
    "months": [
      6,
      7,
      8
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/0a2463a1ce4a4893b846da66f02e3f34"
    ],
    "source_note": "林業及自然保育署記載：6~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "穗花棋盤腳",
    "months": [
      7,
      8
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/0a2463a1ce4a4893b846da66f02e3f34"
    ],
    "source_note": "林業及自然保育署記載：7~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "竹柏",
    "months": [
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/c33ffc117e094727be5acbf2366088d2"
    ],
    "source_note": "林業及自然保育署記載：3~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "竹柏",
    "months": [
      10,
      11
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/c33ffc117e094727be5acbf2366088d2"
    ],
    "source_note": "林業及自然保育署記載：10~11月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "紅淡比",
    "months": [
      1,
      2,
      3,
      4,
      5,
      6
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/ff7e3575498f43d1926c2e0c166a05cf"
    ],
    "source_note": "林業及自然保育署記載：1~6月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "紅淡比",
    "months": [
      7,
      8,
      9
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/ff7e3575498f43d1926c2e0c166a05cf"
    ],
    "source_note": "林業及自然保育署記載：7~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台東漆",
    "months": [
      7,
      8,
      9
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/e75ab564d46c4f4ab69be1a06ee495b9"
    ],
    "source_note": "林業及自然保育署記載：7~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台東漆",
    "months": [
      10,
      11
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/e75ab564d46c4f4ab69be1a06ee495b9"
    ],
    "source_note": "林業及自然保育署記載：10~11月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣三角楓",
    "months": [
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/0212f8757bc84102a0189c06015216e3"
    ],
    "source_note": "林業及自然保育署記載：3~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣三角楓",
    "months": [
      7,
      8,
      9
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/0212f8757bc84102a0189c06015216e3"
    ],
    "source_note": "林業及自然保育署記載：7~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣二葉松",
    "months": [
      2,
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/d2b1556028f24bdbb362b3a012651af3"
    ],
    "source_note": "林業及自然保育署記載：2~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣二葉松",
    "months": [
      1,
      2,
      3,
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/d2b1556028f24bdbb362b3a012651af3"
    ],
    "source_note": "林業及自然保育署記載：10~3月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣五葉松",
    "months": [
      3,
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/a49655f32f0d4b18aa1e7f0e5752a5bf"
    ],
    "source_note": "林業及自然保育署記載：3~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣五葉松",
    "months": [
      1,
      9,
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/a49655f32f0d4b18aa1e7f0e5752a5bf"
    ],
    "source_note": "林業及自然保育署記載：9~1月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣欒樹",
    "months": [
      8,
      9,
      10
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/89fb5ab2a2c74085a021fc298549e69c"
    ],
    "source_note": "林業及自然保育署記載：8~10月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣欒樹",
    "months": [
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/89fb5ab2a2c74085a021fc298549e69c"
    ],
    "source_note": "林業及自然保育署記載：10~12月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣海桐",
    "months": [
      6,
      7,
      8,
      9
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/ab2040fbffb444ea92e97b1c2766e4c8"
    ],
    "source_note": "林業及自然保育署記載：6~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣海桐",
    "months": [
      9,
      10
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/ab2040fbffb444ea92e97b1c2766e4c8"
    ],
    "source_note": "林業及自然保育署記載：9~10月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣海棗",
    "months": [
      3,
      4,
      5,
      6
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/3c96d6b2b0484a7aa08e07031b58d534"
    ],
    "source_note": "林業及自然保育署記載：3~6月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣海棗",
    "months": [
      7,
      8,
      9
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/3c96d6b2b0484a7aa08e07031b58d534"
    ],
    "source_note": "林業及自然保育署記載：7~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣石楠",
    "months": [
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/fcffc8645e7e4a14b04d0de3d1ecab02"
    ],
    "source_note": "林業及自然保育署記載：3~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣石楠",
    "months": [
      1,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/fcffc8645e7e4a14b04d0de3d1ecab02"
    ],
    "source_note": "林業及自然保育署記載：12~1月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣肖楠",
    "months": [
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/2a547e7af67f4d9c8e2e0a526ee6fbcb"
    ],
    "source_note": "林業及自然保育署記載：3~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣肖楠",
    "months": [
      5,
      6,
      7,
      8,
      9,
      10
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/2a547e7af67f4d9c8e2e0a526ee6fbcb"
    ],
    "source_note": "林業及自然保育署記載：5~10月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣赤楠",
    "months": [
      3,
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/518a811a1ac7434abdf62aa97de1ffbc"
    ],
    "source_note": "林業及自然保育署記載：3~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣赤楠",
    "months": [
      9,
      10
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/518a811a1ac7434abdf62aa97de1ffbc"
    ],
    "source_note": "林業及自然保育署記載：9~10月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "蘭嶼羅漢松",
    "months": [
      3,
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/1a9d860250df45098c79b0e0dafcf48f"
    ],
    "source_note": "林業及自然保育署記載：3~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "蘭嶼羅漢松",
    "months": [
      6,
      7,
      8
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/1a9d860250df45098c79b0e0dafcf48f"
    ],
    "source_note": "林業及自然保育署記載：6~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "蘭嶼肉桂",
    "months": [
      2,
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/09f013d1829c4e69a74ff22508f278e3"
    ],
    "source_note": "林業及自然保育署記載：2~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "蘭嶼肉桂",
    "months": [
      7,
      8,
      9
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/09f013d1829c4e69a74ff22508f278e3"
    ],
    "source_note": "林業及自然保育署記載：7~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "象牙樹",
    "months": [
      4,
      5,
      6
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/3861c58640c34a2d876e3394755b8b6d"
    ],
    "source_note": "林業及自然保育署記載：4~6月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "象牙樹",
    "months": [
      7,
      8
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/3861c58640c34a2d876e3394755b8b6d"
    ],
    "source_note": "林業及自然保育署記載：7~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "賽赤楠",
    "months": [
      3,
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/63834923e34242439f9aa8dee844cffa"
    ],
    "source_note": "林業及自然保育署記載：3~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "賽赤楠",
    "months": [
      5,
      6,
      7,
      8
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/63834923e34242439f9aa8dee844cffa"
    ],
    "source_note": "林業及自然保育署記載：5~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "軟毛柿",
    "months": [
      7,
      8
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/eb6bb9a016684a37a44b3e14fcefc23c"
    ],
    "source_note": "林業及自然保育署記載：7~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "軟毛柿",
    "months": [
      1,
      2,
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/eb6bb9a016684a37a44b3e14fcefc23c"
    ],
    "source_note": "林業及自然保育署記載：10~2月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "鐵冬青",
    "months": [
      4,
      5,
      6
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/4dc0e5ef1b844dc9a4384e9601ba9447"
    ],
    "source_note": "林業及自然保育署記載：4~6月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "鐵冬青",
    "months": [
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/4dc0e5ef1b844dc9a4384e9601ba9447"
    ],
    "source_note": "林業及自然保育署記載：10~12月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "青剛櫟",
    "months": [
      3,
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/99569a20dc104a66bffd13353834d85c"
    ],
    "source_note": "林業及自然保育署記載：3~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "青剛櫟",
    "months": [
      1,
      2,
      8,
      9,
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/99569a20dc104a66bffd13353834d85c"
    ],
    "source_note": "林業及自然保育署記載：8~2月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "青楓",
    "months": [
      6,
      7,
      8
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/d9b3af3a4cf040b2bdac1146a07f5ade"
    ],
    "source_note": "林業及自然保育署記載：6~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "青楓",
    "months": [
      10,
      11
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/d9b3af3a4cf040b2bdac1146a07f5ade"
    ],
    "source_note": "林業及自然保育署記載：10~11月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "風箱樹",
    "months": [
      3,
      4,
      5
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/b9990b95b47f48fda2e3b64b8b56b0cb"
    ],
    "source_note": "林業及自然保育署記載：3~5月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "風箱樹",
    "months": [
      7,
      8,
      9
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/b9990b95b47f48fda2e3b64b8b56b0cb"
    ],
    "source_note": "林業及自然保育署記載：7~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "食茱萸",
    "months": [
      7,
      8
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/9acb2d930d314dfea71af1ee426d8c72"
    ],
    "source_note": "林業及自然保育署記載：7~8月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "食茱萸",
    "months": [
      9,
      10,
      11
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/9acb2d930d314dfea71af1ee426d8c72"
    ],
    "source_note": "林業及自然保育署記載：9~11月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "香楠",
    "months": [
      2,
      3
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/648d4a241e5c49d398c0c44dc8ea8e9d"
    ],
    "source_note": "林業及自然保育署記載：2~3月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "香楠",
    "months": [
      4,
      5,
      6
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/648d4a241e5c49d398c0c44dc8ea8e9d"
    ],
    "source_note": "林業及自然保育署記載：4~6月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "魚木",
    "months": [
      8,
      9,
      10,
      11
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/8ccc62a5f77a4c849a11d5e2429e4816"
    ],
    "source_note": "林業及自然保育署記載：8~11月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "魚木",
    "months": [
      9,
      10,
      11,
      12
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/8ccc62a5f77a4c849a11d5e2429e4816"
    ],
    "source_note": "林業及自然保育署記載：9~12月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "黃槿",
    "months": [
      4,
      5,
      6,
      7,
      8,
      9
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/bb5215fe23c840dab82e470de9bbcc7d"
    ],
    "source_note": "林業及自然保育署記載：4~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "黃槿",
    "months": [
      7,
      8,
      9
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/bb5215fe23c840dab82e470de9bbcc7d"
    ],
    "source_note": "林業及自然保育署記載：7~9月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "黃連木",
    "months": [
      4
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "記錄當地開花與落花情況，依實際狀況維持通行空間整潔。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/2aad60f9d99d4896b1869e447ec8df79"
    ],
    "source_note": "林業及自然保育署記載：4~4月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "黃連木",
    "months": [
      9,
      10
    ],
    "rule_type": "fruit",
    "event": "果期觀察參考",
    "action": "觀察果實成熟及地面落果，依現場狀況評估清潔需求。",
    "source_urls": [
      "https://nativetree.forest.gov.tw/Tree/Info/2aad60f9d99d4896b1869e447ec8df79"
    ],
    "source_note": "林業及自然保育署記載：9~10月。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "榕樹",
    "months": [
      4,
      5,
      6,
      7,
      8,
      9,
      10
    ],
    "rule_type": "assessment",
    "event": "季節養護評估參考",
    "action": "由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=4"
    ],
    "source_note": "臺北市公園處歷史修剪示範月曆，PDF 第 4 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "樟樹",
    "months": [
      3,
      4
    ],
    "rule_type": "assessment",
    "event": "季節養護評估參考",
    "action": "由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=4"
    ],
    "source_note": "臺北市公園處歷史修剪示範月曆，PDF 第 4 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "茄苳",
    "months": [
      1,
      2,
      12
    ],
    "rule_type": "assessment",
    "event": "季節養護評估參考",
    "action": "由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=8"
    ],
    "source_note": "臺北市公園處歷史修剪示範月曆，PDF 第 8 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "台灣欒樹",
    "months": [
      1,
      2,
      12
    ],
    "rule_type": "assessment",
    "event": "季節養護評估參考",
    "action": "由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=8"
    ],
    "source_note": "臺北市公園處歷史修剪示範月曆，PDF 第 8 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "白千層",
    "months": [
      3,
      4
    ],
    "rule_type": "assessment",
    "event": "季節養護評估參考",
    "action": "由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=12"
    ],
    "source_note": "臺北市公園處歷史修剪示範月曆，PDF 第 12 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "楓香",
    "months": [
      1,
      2,
      12
    ],
    "rule_type": "assessment",
    "event": "季節養護評估參考",
    "action": "由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=12"
    ],
    "source_note": "臺北市公園處歷史修剪示範月曆，PDF 第 12 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "黑板樹",
    "months": [
      4,
      5,
      6,
      7,
      8,
      9,
      10
    ],
    "rule_type": "assessment",
    "event": "季節養護評估參考",
    "action": "由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=16"
    ],
    "source_note": "臺北市公園處歷史修剪示範月曆，PDF 第 16 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "阿勃勒",
    "months": [
      6,
      7,
      8,
      9,
      10
    ],
    "rule_type": "assessment",
    "event": "季節養護評估參考",
    "action": "由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=20"
    ],
    "source_note": "臺北市公園處歷史修剪示範月曆，PDF 第 20 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "印度紫檀",
    "months": [
      6,
      7,
      8,
      9,
      10
    ],
    "rule_type": "assessment",
    "event": "季節養護評估參考",
    "action": "由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=20"
    ],
    "source_note": "臺北市公園處歷史修剪示範月曆，PDF 第 20 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "大王椰子",
    "months": [
      5,
      6,
      7,
      8,
      9,
      10
    ],
    "rule_type": "assessment",
    "event": "季節養護評估參考",
    "action": "由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=24"
    ],
    "source_note": "臺北市公園處歷史修剪示範月曆，PDF 第 24 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "蒲葵",
    "months": [
      5,
      6,
      7,
      8,
      9,
      10
    ],
    "rule_type": "assessment",
    "event": "季節養護評估參考",
    "action": "由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=24"
    ],
    "source_note": "臺北市公園處歷史修剪示範月曆，PDF 第 24 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "木棉",
    "months": [
      2,
      3
    ],
    "rule_type": "flower",
    "event": "花期觀察參考",
    "action": "觀察開花及落花，依現場情況維持通行空間整潔。",
    "source_urls": [
      "https://zzdo.gov.taipei/cp.aspx?n=4603E2443E2D75D8"
    ],
    "source_note": "臺北市中正區公所記載 2–3 月先花後葉；實際花期依當年氣候觀察。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "木棉",
    "months": [
      5
    ],
    "rule_type": "fruit",
    "event": "果實棉絮觀察參考",
    "action": "觀察果實及棉絮，依實際落果、棉絮情況評估清潔及通行維護。",
    "source_urls": [
      "https://zzdo.gov.taipei/cp.aspx?n=4603E2443E2D75D8"
    ],
    "source_note": "區公所記載約 5 月棉絮散布；不據此自動安排摘果或修剪。",
    "evidence_level": "reference",
    "enabled": true
  },
  {
    "species_key": "小葉欖仁",
    "months": [],
    "rule_type": "flower",
    "event": "花期資料待確認",
    "action": "官方來源記載月份不同，先建立臺北在地觀察紀錄，確認後再啟用月份規則。",
    "source_urls": [
      "https://kmweb.moa.gov.tw/subject/subject.php?id=27041",
      "https://pwbpo.kcg.gov.tw/News_Content.aspx?n=A861811798A0B9C7&s=598D5FB950E3746F&sms=5B2116A2A2920C77"
    ],
    "source_note": "農業知識入口網記載 3–5 月，高雄市公園處記載 9–11 月；樹種學名及區域適用性需專家核對。",
    "evidence_level": "conflict",
    "enabled": false
  },
  {
    "species_key": "小葉欖仁",
    "months": [],
    "rule_type": "assessment",
    "event": "養護月份待現地確認",
    "action": "依當地落葉與萌芽情況評估；歷史月曆圖與文字適期不完全一致，暫不給固定月份。",
    "source_urls": [
      "https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf#page=16"
    ],
    "source_note": "歷史文件文字與月曆圖不完全一致；保留衝突，未啟用。",
    "evidence_level": "conflict",
    "enabled": false
  }
]
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
