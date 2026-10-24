-- Additive, server-only storage. Existing tables are not modified.
begin;
create table if not exists public.kootree_imports (
  id uuid primary key,
  dataset text not null check (dataset in ('trees', 'official_cases')),
  row_count integer not null check (row_count >= 0),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique (dataset, id)
);
create table if not exists public.kootree_rows (
  import_id uuid not null references public.kootree_imports(id),
  ordinal integer not null check (ordinal >= 0),
  payload jsonb not null,
  primary key (import_id, ordinal)
);
create table if not exists public.kootree_active_datasets (
  dataset text primary key,
  import_id uuid not null,
  foreign key (dataset, import_id) references public.kootree_imports(dataset, id)
);
alter table public.kootree_imports enable row level security;
alter table public.kootree_rows enable row level security;
alter table public.kootree_active_datasets enable row level security;
revoke all on public.kootree_imports, public.kootree_rows, public.kootree_active_datasets from anon, authenticated;
grant select, insert on public.kootree_imports, public.kootree_rows to service_role;
grant select, insert, update on public.kootree_active_datasets to service_role;

create or replace function public.kootree_activate_import(snapshot_id uuid)
returns void language plpgsql security invoker set search_path = '' as $$
declare batch public.kootree_imports%rowtype;
begin
  select * into strict batch from public.kootree_imports where id = snapshot_id;
  if (select count(*) from public.kootree_rows where import_id = snapshot_id) <> batch.row_count then
    raise exception 'Import incomplete; previous active snapshot retained';
  end if;
  insert into public.kootree_active_datasets(dataset, import_id) values (batch.dataset, batch.id)
  on conflict (dataset) do update set import_id = excluded.import_id;
end;
$$;
revoke all on function public.kootree_activate_import(uuid) from public, anon, authenticated;
grant execute on function public.kootree_activate_import(uuid) to service_role;
commit;
