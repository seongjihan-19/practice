-- =====================================================================
-- 가상 상품 데이터 (실습 전용) — schema.sql 실행 후 실행
-- 원본: docs/dummy/products_db.xlsx (상품 문서 10건 기반, 상품명·가격·정책은 전부 가상)
-- 기존 데이터를 모두 비우고 다시 넣으므로 여러 번 실행해도 된다
-- 전체가 한 트랜잭션이라 중간에 오류가 나면 기존 데이터가 그대로 남는다
-- =====================================================================

begin;

-- 기존 데이터 비우기 (identity 번호도 1부터 다시 시작)
truncate table
  public.product_allergens,
  public.product_notes,
  public.storage_periods,
  public.shipping_policies,
  public.products
restart identity;

insert into public.products
  (product_code, product_name, category, origin, ingredients, allergen_status, net_amount, unit, pack_count, price_krw, sale_season, description)
values
  ('P-0113', '대구사과칩',        '가공-건조', '대구 팔공산',       '사과 100%',                          '미기재', 60,  'g',  null,      4900,  '상시',  '저온 건조. 설탕·첨가물 없음. 글루텐 없음'),
  ('P-0127', '팔공산 꿀사과',     '농산물',    '대구 팔공산',       '사과(부사)',                         '없음',   2,   'kg', '7~9개',   18000, '상시',  '해발 400m 과수원. 당도 14Brix 이상 선별. 왁스 코팅 없음'),
  ('P-0205', '성주 참외',         '농산물',    '경북 성주',         '참외',                               '없음',   1.5, 'kg', '5~6개',   12000, '4~7월', '하우스 참외 특품'),
  ('P-0207', '참외청',            '가공-액상', '경북 성주',         '참외(경북 성주)·비정제 원당(국내산)', '없음',   350, 'ml', null,      9500,  '상시',  '참외와 비정제 원당을 1:1로 재운 청'),
  ('P-0305', '청도 반건시',       '가공-건조', '경북 청도',         '감',                                 '없음',   500, 'g',  '10개',    15000, '상시',  '20일 자연 건조. 겉은 쫀득, 속은 촉촉'),
  ('P-0312', '의성 마늘',         '농산물',    '경북 의성',         '마늘(한지형)',                       '없음',   1,   'kg', '약 15통', 11000, '상시',  '알이 단단하고 매운맛이 강함'),
  ('P-0318', '흑마늘 진액',       '가공-액상', '경북 의성',         '흑마늘(경북 의성)·정제수',           '없음',   70,  'ml', '30포',    24000, '상시',  '의성 마늘을 15일 숙성한 추출액'),
  ('P-0402', '서문시장 납작만두', '냉동',      null,                '밀가루·당면·부추·대두(간장)',        '있음',   500, 'g',  '20개',    7900,  '상시',  '서문시장식. 당면·부추 소, 간장 양념 포함'),
  ('P-0410', '달성 토마토',       '농산물',    '대구 달성(하빈면)', '토마토',                             '없음',   1,   'kg', '6~8개',   8500,  '상시',  '완숙. 산도가 낮아 생식용'),
  ('P-0421', '경산 대추칩',       '가공-건조', '경북 경산',         '대추 100%',                          '미기재', 50,  'g',  null,      5500,  '상시',  '씨를 뺀 대추를 말린 칩');

insert into public.storage_periods (product_code, stage, storage_type, duration, duration_unit)
values
  ('P-0113', '개봉 전', '상온', 6,  '개월'),
  ('P-0113', '개봉 후', '상온', 7,  '일'),
  ('P-0127', '수령 후', '냉장', 3,  '주'),
  ('P-0127', '수령 후', '상온', 7,  '일'),
  ('P-0205', '수령 후', '냉장', 5,  '일'),
  ('P-0207', '개봉 전', '상온', 12, '개월'),
  ('P-0207', '개봉 후', '냉장', 30, '일'),
  ('P-0305', '수령 후', '냉장', 10, '일'),
  ('P-0312', '수령 후', '상온', 2,  '개월'),
  ('P-0318', '개봉 전', '상온', 18, '개월'),
  ('P-0402', '수령 후', '냉동', 3,  '개월'),
  ('P-0410', '수령 후', '상온', 3,  '일'),
  ('P-0410', '수령 후', '냉장', 7,  '일'),
  ('P-0421', '개봉 후', '상온', 14, '일');

insert into public.product_notes (product_code, note_type, content, reason)
values
  ('P-0113', '금지',     '냉장 보관 금지',                                       '습기를 먹어 눅눅해짐'),
  ('P-0113', '보관팁',   '개봉 후 밀봉해 서늘한 곳에 보관',                      null),
  ('P-0127', '금지',     '다른 과일과 함께 보관 금지',                           '에틸렌으로 다른 과일이 빨리 익음'),
  ('P-0205', '섭취안내', '받은 날부터 3일 안에 섭취 권장',                       '꼭지가 마르면 당도가 떨어짐'),
  ('P-0207', '금지',     '금속 숟가락 사용 금지',                                '발효가 빨라짐'),
  ('P-0207', '보관팁',   '나무 또는 플라스틱 숟가락 사용',                       null),
  ('P-0207', '섭취안내', '탄산수에 1:4로 희석',                                  null),
  ('P-0305', '금지',     '냉동 보관 금지',                                       '해동하면 수분이 빠져 질겨짐'),
  ('P-0305', '보관팁',   '받은 즉시 냉장',                                       null),
  ('P-0305', '참고',     '표면의 흰 가루는 당분이 굳은 것으로 정상',             null),
  ('P-0312', '금지',     '비닐봉지 밀봉 금지',                                   '곰팡이가 생김'),
  ('P-0312', '금지',     '냉장 보관 금지',                                       '싹이 남'),
  ('P-0312', '보관팁',   '통풍이 잘 되는 그늘에 망으로 보관',                    null),
  ('P-0318', '섭취안내', '하루 1포 권장',                                        null),
  ('P-0318', '섭취안내', '개봉한 포는 당일 섭취',                                null),
  ('P-0318', '보관팁',   '여름철에는 냉장 보관 권장',                            null),
  ('P-0318', '섭취주의', '임산부·수술 전후는 섭취 전 전문가 상담',               null),
  ('P-0402', '금지',     '전자레인지 조리 금지',                                 '피가 질겨짐'),
  ('P-0402', '조리',     '해동하지 말고 냉동 상태로 팬에 기름 두르고 중불 3분',  null),
  ('P-0410', '보관팁',   '꼭지를 아래로 두고 보관',                              '수분 증발을 줄임'),
  ('P-0410', '섭취안내', '냉장 보관 후 먹기 30분 전에 꺼내기',                   '맛이 돌아옴'),
  ('P-0421', '보관팁',   '실리카겔을 버리지 않기',                               '습기에 약함'),
  ('P-0421', '섭취안내', '차로 우려 마시기(80℃ 물 300ml에 5조각)',               null);

insert into public.product_allergens (product_code, allergen, contact_type)
values
  ('P-0113', '견과류', '교차오염'),
  ('P-0402', '밀',     '함유'),
  ('P-0402', '대두',   '함유'),
  ('P-0402', '계란',   '교차오염'),
  ('P-0421', '견과류', '교차오염');

insert into public.shipping_policies (policy_key, label, value)
values
  ('same_day_areas',      '당일배송지역',     '수성구, 달서구'),
  ('same_day_cutoff',     '당일배송마감',     '오후 2시 이전 주문'),
  ('other_areas',         '그 외 지역',       '익일 배송'),
  ('free_shipping_min',   '무료배송기준',     '30,000원 이상'),
  ('base_shipping_fee',   '기본배송비',       '2,500원 (30,000원 미만)'),
  ('fresh_dispatch_days', '신선식품발송요일', '월~목 (금요일 주문은 다음 주 월요일 발송)');

commit;

-- ---------------------------------------------------------------------
-- 실행 후 확인용 (따로 실행)
-- ---------------------------------------------------------------------
-- 행 수: products 10 / storage_periods 14 / product_notes 23 / product_allergens 5 / shipping_policies 6
-- select 'products' t, count(*) from public.products
-- union all select 'storage_periods', count(*) from public.storage_periods
-- union all select 'product_notes', count(*) from public.product_notes
-- union all select 'product_allergens', count(*) from public.product_allergens
-- union all select 'shipping_policies', count(*) from public.shipping_policies;
--
-- allergen_status와 알레르기 함유 행이 어긋난 상품 (결과가 비어 있어야 정상)
-- select p.product_code, p.allergen_status
--   from public.products p
--  where (p.allergen_status = '있음') <> exists (
--          select 1 from public.product_allergens a
--           where a.product_code = p.product_code and a.contact_type = '함유');
--
-- 상품 한눈에 보기
-- select * from public.product_overview where product_code = 'P-0402';

