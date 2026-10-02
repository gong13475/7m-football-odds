# ⚽ 7M 축구 최종배당 수집기

7M 1X2 결과 페이지에서 경기 결과와 최종 1X2 배당을 수집하고,
동일한 최종배당의 과거 승/무/패 결과를 분석하는 Streamlit 앱입니다.

## 구성

- `app.py`
- `collector.py`
- `database.py`
- `analyzer.py`
- `retry_manager.py`
- `worker.py`
- `requirements.txt`
- `README.md`

## 수집 URL

기본 주소:

https://1x2.7mkr.com/result_kr.shtml

날짜:

`?cid=&dt=YYYY-MM-DD`

예:

`result_kr.shtml?cid=&dt=2026-02-01`

## 배당 처리

페이지의 경기 데이터에서

1. 최초 배당
2. 경기 결과
3. 비교
4. 최종 배당

구조를 확인하고,

`비교` 이후의 1X2 배당을 최종배당으로 저장합니다.

## 결과 코드

- H = 홈승
- D = 무승부
- A = 원정승

## 저장

SQLite:

`odds.db`

중복 경기는 자동으로 무시합니다.

## 재시도

네트워크 오류가 발생하면 최대 3회 재시도합니다.

요청 사이에는 지연시간을 둡니다.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
