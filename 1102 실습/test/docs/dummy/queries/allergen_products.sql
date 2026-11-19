-- =====================================================================
-- 알레르기가 있는 상품 조회 (실습 전용)
-- 전제: schema.sql → seed.sql 실행 완료
-- 함유 여부가 문서에 없는 상품(allergen_status = '미기재')은 모든 쿼리에서 제외
-- 쿼리 3개는 서로 독립적이다. 필요한 것만 골라 실행
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. 알레르기가 있는 상품 전체 (함유 + 교차오염), 상품 하나당 한 행
--    예상 결과 1행: P-0402 (함유 대두, 밀 / 교차오염 계란)
-- ---------------------------------------------------------------------
select
  p.product_code                                                                       as "상품코드",
  p.product_name                                                                       as "상품명",
  p.allergen_status                                                                    as "함유 표시",
  string_agg(a.allergen, ', ' order by a.allergen) filter (where a.contact_type = '함유')     as "함유 물질",
  string_agg(a.allergen, ', ' order by a.allergen) filter (where a.contact_type = '교차오염') as "교차오염 물질"
from public.products p
join public.product_allergens a on a.product_code = p.product_code
where p.allergen_status <> '미기재'
group by p.product_code, p.product_name, p.allergen_status
order by p.product_code;


-- ---------------------------------------------------------------------
-- 2. 원재료에 알레르기 물질이 들어 있는 상품만 (교차오염 제외)
--    예상 결과 1행: P-0402 (대두, 밀)
-- ---------------------------------------------------------------------
select
  p.product_code                                   as "상품코드",
  p.product_name                                   as "상품명",
  string_agg(a.allergen, ', ' order by a.allergen) as "함유 물질"
from public.products p
join public.product_allergens a on a.product_code = p.product_code
where a.contact_type = '함유'
  and p.allergen_status <> '미기재'
group by p.product_code, p.product_name
order by p.product_code;


-- ---------------------------------------------------------------------
-- 3. 특정 물질이 있는 상품 (아래 '계란'을 원하는 물질로 바꿔 실행)
--    예상 결과 1행: P-0402 (교차오염)
--    참고: '견과류'로 바꾸면 결과가 없다. 견과류 교차오염 상품(P-0113 · P-0421)이 둘 다 미기재라 제외됨
-- ---------------------------------------------------------------------
select
  p.product_code  as "상품코드",
  p.product_name  as "상품명",
  a.allergen      as "물질",
  a.contact_type  as "구분"
from public.products p
join public.product_allergens a on a.product_code = p.product_code
where a.allergen = '계란'
  and p.allergen_status <> '미기재'
order by p.product_code;
