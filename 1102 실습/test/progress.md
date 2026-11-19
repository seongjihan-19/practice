# 진행 기록

## 2026-11-02 — 가상 상품 DB 엑셀 생성

- 산출물: `docs/dummy/products_db.xlsx` (실습 전용, `docs/dummy/` 상품 문서 10건 기반)
- 1차: 상품 한 시트에 20필드 → 신선식품여부 삭제(사용 안 함) → 빈칸이 많아 아래 구조로 변경
- 현재 구조 (시트 6개, `상품코드`로 연결)
  - `상품` 10행 × 12필드: 모든 상품에 있는 정보만. `알레르기함유`(있음 1 / 없음 7 / 미기재 2)로 "없음 명시"와 "미기재"를 구분
  - `보관기간` 14행: 상품코드 · 시점(개봉 전/개봉 후/수령 후) · 보관방식 · 기간(숫자) · 기간단위
  - `안내사항` 23행: 상품코드 · 유형(금지/보관팁/섭취안내/조리/섭취주의/참고) · 내용 · 이유
  - `알레르기` 5행: 상품코드 · 물질 · 구분(함유/교차오염)
  - `배송정책`: 10건 공통 규칙
  - `필드정의`: 시트별 필드명 · 영문 키 · 형식 · 설명
- 정한 기준
  - 카테고리: 농산물 / 가공-건조 / 가공-액상 / 냉동
  - 원문에 없는 정보는 행을 만들지 않음 (예: 대추칩 개봉 전 유통기한)
- 확인한 제약
  - 이 PC의 Excel은 2016(32비트)이라 FILTER · TEXTJOIN 미지원 → 상품별 조회 시트는 만들지 않음, 시트 필터로 대신

## 2026-11-02 — Supabase용 SQL 작성

- 산출물: 실행은 사용자가 Supabase SQL Editor에서 직접, `schema.sql` → `seed.sql` 순서
  - `docs/dummy/schema.sql`: 테이블 · 제약 · 인덱스 · 뷰 · RLS (처음 한 번)
  - `docs/dummy/seed.sql`: truncate 후 데이터 입력, 여러 번 실행 가능 + 확인용 쿼리
  - 처음엔 `supabase_products.sql` 한 파일이었으나 위 두 파일로 나누고 삭제
  - 테이블 5개: products · storage_periods · product_notes · product_allergens · shipping_policies
  - 뷰 `product_overview`: 상품 하나를 한 행으로 모아 보기 (엑셀에서 못 만든 조회 시트 대체)
  - RLS 켜고 anon · authenticated에 읽기만 허용
  - 목록형 값은 CHECK 제약으로 제한, 하위 테이블은 product_code 외래키(삭제 시 함께 삭제)
- 엑셀과 다른 점: 만두 산지 "미기재(서문시장식)" → null, "서문시장식"은 description으로 옮김
- 검증: 입력 행 수 · 안내사항 내용 엑셀과 대조 완료. 이 PC에 psql이 없어 SQL 실행 검증은 못 함

## 2026-11-02 — 알레르기 상품 조회 쿼리

- 산출물: `docs/dummy/queries/allergen_products.sql` (쿼리 3개, 각각 따로 실행)
  - 1 알레르기 있는 상품 전체(함유·교차오염 나눠 표시) / 2 함유만 / 3 특정 물질(계란 예시)
  - 요청에 따라 allergen_status = '미기재' 상품은 모든 쿼리에서 제외 → 결과는 P-0402만
  - 미기재 상품만 보던 4번 쿼리는 요청과 반대라 삭제
  - 주의: 이 조건 때문에 사과칩 · 대추칩의 견과류 교차오염도 조회되지 않음
- 검증: seed.sql 데이터로 예상 결과를 손으로 대조해 주석에 적음. 실제 실행은 사용자가 Supabase에서

## 2026-11-02 — 상품 관리 웹앱 (React, 로컬 전용)

- 산출물: `product-admin/` (Vite + React 19 + supabase-js, 실행 방법은 `product-admin/README.md`)
  - 조회(목록 + 상세) · 검색(텍스트 · 카테고리 · 알레르기 함유) · 추가(하위 행 포함) · 삭제(하위 행 cascade)
  - 쓰기 권한: service_role 키 사용 (사용자 선택). 127.0.0.1에서만 열림
  - 실행: `상품관리 실행.bat` 더블클릭 → 패키지 자동 설치(처음) · 서버 실행 · 브라우저 열기
  - 연결: 첫 화면에서 URL · 키를 붙여 넣으면 연결 시험 후 localStorage에 저장. `.env.local`은 선택 사항. 연결 해제 버튼으로 삭제
  - `.env.local`: URL · anon 키(조회) · service_role 키(추가 · 삭제) 3개 변수. service_role이 없으면 읽기 전용
    - 기존 Session pooler 설정 2줄은 주석으로 막아 파일 아래에 남김 (내용은 열어 보지 않음). 세 값은 비어 있어 사용자가 채워야 함
  - 앱 코드에는 상품 데이터를 넣지 않음. 데이터는 전부 Supabase에서 읽음
- 환경: winget으로 Node.js v26.13.0 설치 (새 터미널부터 PATH 적용)
- 검증: 빌드 성공. 가짜 Supabase 서버(테스트 상품 2건)로 조회 · 검색 · 추가(중복 코드 등 입력 검사 포함) · 삭제를 브라우저에서 확인
  - bat 실행 → 서버 기동 · 연결 화면 확인. 틀린 키 안내 문구, 연결 후 새로고침 유지, 연결 해제 시 저장값 삭제 확인
  - anon만 → 읽기 전용(추가 · 삭제 버튼 없음), anon + service_role → 추가 · 삭제 버튼 표시 확인
  - 참고: 백그라운드로 띄운 Vite는 작업을 멈춰도 node 프로세스가 남음 → 테스트 후 포트로 찾아 종료할 것
- `.env.local` 값 입력 완료: anon · service_role 모두 접속 성공, products 10건 조회 확인
- GitHub: `product-admin/`을 git 저장소로 만들고 README.md만 커밋해 https://github.com/seongjihan-19/foodlist (main)에 push
  - 이어서 앱 소스 전체 16개 파일 커밋 · push (3be18d8). `.env.local` · node_modules는 .gitignore로 제외 확인
- Vercel 배포(foodlist-eight.vercel.app, 사용자가 연결)에 맞춰 수정
  - 배포 빌드: 연결 입력 화면 제거, 환경 변수 URL · anon 키로 읽기 전용. service_role 키는 DEV에서만 읽어 배포 결과물에 안 들어감
  - 검증: 가짜 키로 배포 빌드 → service_role 표시값 · 연결 화면 코드 미포함, 미리보기에서 읽기 전용 목록 확인
  - 남은 일: 사용자가 Vercel Environment Variables에 URL · anon 키 추가 후 Redeploy
  - 실제 Supabase 연결은 키가 없어 미확인

## 남은 일
  - 실제 DB로 옮길 때 `필드정의`의 영문 키를 컬럼명으로 사용
