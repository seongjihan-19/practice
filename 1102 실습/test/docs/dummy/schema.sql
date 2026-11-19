-- =====================================================================
-- 가상 상품 DB 스키마 (실습 전용) — Supabase SQL Editor에서 처음 한 번 실행
-- 테이블: products / storage_periods / product_notes / product_allergens / shipping_policies
-- 뷰:     product_overview (상품 하나의 정보를 한 행으로 모아 보기)
-- 실행 순서: schema.sql → seed.sql
-- 전체가 한 트랜잭션이라 중간에 오류가 나면 아무것도 만들어지지 않는다
-- =====================================================================

begin;

-- ---------------------------------------------------------------------
-- 1. 상품: 모든 상품에 있는 정보
-- ---------------------------------------------------------------------
create table public.products (
  product_code    text primary key check (product_code ~ '^P-[0-9]{4}$'),
  product_name    text not null,
  category        text not null check (category in ('농산물', '가공-건조', '가공-액상', '냉동')),
  origin          text,                 -- 문서에 없으면 null
  ingredients     text not null,
  allergen_status text not null check (allergen_status in ('있음', '없음', '미기재')),
  net_amount      numeric(10, 2) not null check (net_amount > 0),
  unit            text not null check (unit in ('g', 'kg', 'ml')),
  pack_count      text,                 -- 개수·포 수, 없으면 null
  price_krw       integer not null check (price_krw >= 0),
  sale_season     text not null default '상시',
  description     text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

comment on table  public.products is '상품 기본 정보 (실습용 가상 데이터)';
comment on column public.products.product_code    is '상품코드, P-0000 형식. 다른 테이블과 연결하는 키';
comment on column public.products.category        is '농산물 / 가공-건조 / 가공-액상 / 냉동';
comment on column public.products.origin          is '산지. 문서에 없으면 null';
comment on column public.products.allergen_status is '있음(product_allergens에 함유 행) / 없음(문서에 없음으로 명시) / 미기재(문서에 언급 없음). 교차오염은 product_allergens 참고';
comment on column public.products.net_amount      is '용량. 묶음 상품은 1개(1포) 기준';
comment on column public.products.pack_count      is '입수(개수·포 수)';
comment on column public.products.sale_season     is '상시 또는 판매 월';

-- ---------------------------------------------------------------------
-- 2. 보관기간: 상품별 보관 조건 하나당 한 행
-- ---------------------------------------------------------------------
create table public.storage_periods (
  id            bigint generated always as identity primary key,
  product_code  text not null references public.products (product_code) on update cascade on delete cascade,
  stage         text not null check (stage in ('개봉 전', '개봉 후', '수령 후')),
  storage_type  text not null check (storage_type in ('상온', '냉장', '냉동')),
  duration      integer not null check (duration > 0),
  duration_unit text not null check (duration_unit in ('일', '주', '개월')),
  unique (product_code, stage, storage_type)
);

comment on table  public.storage_periods is '상품별 보관 기간';
comment on column public.storage_periods.stage is '개봉 전 / 개봉 후 / 수령 후(농산물·냉동처럼 개봉 개념이 없는 상품)';

create index storage_periods_product_code_idx on public.storage_periods (product_code);

-- ---------------------------------------------------------------------
-- 3. 안내사항: 금지·보관팁·섭취안내 등 상품별 안내 하나당 한 행
-- ---------------------------------------------------------------------
create table public.product_notes (
  id           bigint generated always as identity primary key,
  product_code text not null references public.products (product_code) on update cascade on delete cascade,
  note_type    text not null check (note_type in ('금지', '보관팁', '섭취안내', '조리', '섭취주의', '참고')),
  content      text not null,
  reason       text                    -- 원문에 이유가 있을 때만
);

comment on table  public.product_notes is '상품별 보관·섭취·조리 안내';
comment on column public.product_notes.note_type is '금지 / 보관팁 / 섭취안내 / 조리 / 섭취주의 / 참고';

create index product_notes_product_code_idx on public.product_notes (product_code);

-- ---------------------------------------------------------------------
-- 4. 알레르기: 상품별 알레르기 물질 하나당 한 행
-- ---------------------------------------------------------------------
create table public.product_allergens (
  product_code text not null references public.products (product_code) on update cascade on delete cascade,
  allergen     text not null,
  contact_type text not null check (contact_type in ('함유', '교차오염')),
  primary key (product_code, allergen, contact_type)
);

comment on table  public.product_allergens is '상품별 알레르기 물질';
comment on column public.product_allergens.contact_type is '함유(원재료에 포함) / 교차오염(같은 생산 라인 사용)';

-- ---------------------------------------------------------------------
-- 5. 배송정책: 전 상품 공통 규칙
-- ---------------------------------------------------------------------
create table public.shipping_policies (
  policy_key text primary key,
  label      text not null,
  value      text not null
);

comment on table public.shipping_policies is '전 상품 공통 배송 정책';

-- ---------------------------------------------------------------------
-- 6. 조회용 뷰: 상품 하나의 정보를 한 행으로
--    security_invoker = 조회하는 사람의 권한(RLS)을 그대로 따름
-- ---------------------------------------------------------------------
create view public.product_overview
with (security_invoker = true) as
select
  p.product_code,
  p.product_name,
  p.category,
  p.origin,
  p.net_amount,
  p.unit,
  p.pack_count,
  p.price_krw,
  p.allergen_status,
  (select string_agg(s.stage || ' ' || s.storage_type || ' ' || s.duration || s.duration_unit, ' / ' order by s.id)
     from public.storage_periods s where s.product_code = p.product_code) as storage_summary,
  (select string_agg(a.allergen || '(' || a.contact_type || ')', ', ' order by a.contact_type, a.allergen)
     from public.product_allergens a where a.product_code = p.product_code) as allergens,
  (select string_agg('[' || n.note_type || '] ' || n.content || coalesce(' — ' || n.reason, ''), E'\n' order by n.id)
     from public.product_notes n where n.product_code = p.product_code) as notes
from public.products p;

-- ---------------------------------------------------------------------
-- 7. RLS: 누구나 읽기만 가능. 쓰기는 대시보드·service_role 키로만
-- ---------------------------------------------------------------------
alter table public.products          enable row level security;
alter table public.storage_periods   enable row level security;
alter table public.product_notes     enable row level security;
alter table public.product_allergens enable row level security;
alter table public.shipping_policies enable row level security;

create policy "공개 읽기" on public.products          for select to anon, authenticated using (true);
create policy "공개 읽기" on public.storage_periods   for select to anon, authenticated using (true);
create policy "공개 읽기" on public.product_notes     for select to anon, authenticated using (true);
create policy "공개 읽기" on public.product_allergens for select to anon, authenticated using (true);
create policy "공개 읽기" on public.shipping_policies for select to anon, authenticated using (true);

commit;

-- ---------------------------------------------------------------------
-- 처음부터 다시 만들 때 (주의: 데이터가 모두 지워짐, 따로 실행)
-- ---------------------------------------------------------------------
-- drop view  if exists public.product_overview;
-- drop table if exists public.product_allergens, public.product_notes, public.storage_periods, public.shipping_policies, public.products;
