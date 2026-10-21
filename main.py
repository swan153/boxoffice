import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

# 2. 한국 표준시(KST) 기준 어제 날짜 계산
# 서버 시계(UTC 등)와 상관없이 한국 시간을 기준으로 계산합니다.
kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.datetime.now(kst)
yesterday_kst = now_kst - datetime.timedelta(days=1)
target_date_str = yesterday_kst.strftime('%Y%m%d')       # API 요청용 (YYYYMMDD)
formatted_date_str = yesterday_kst.strftime('%Y년 %m월 %d일') # 화면 표시용

# 헤더 타이틀 출력
st.title("🎬 어제의 박스오피스")
st.caption(f"기준일: {formatted_date_str} (한국 시간 기준)")

# 3. Streamlit Secrets에서 API 키 불러오기
# Streamlit Cloud의 Secrets 설정에서 KOBIS_KEY를 지정해야 합니다.
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키가 설정되지 않았습니다.")
    st.info("""
    **확인해 주세요:**
    1. Streamlit Cloud 앱 설정의 **Secrets** 항목을 확인해 주세요.
    2. `KOBIS_KEY = "발급받은_키"` 형태로 입력되어 있는지 확인해 주세요.
    """)
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 4. KOBIS API 데이터 요청
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_date_str
}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException as e:
    st.error("📡 API 서버와의 통신 중 오류가 발생했습니다.")
    st.info("""
    **확인해 주세요:**
    1. 인터넷 연결 상태를 확인해 주세요.
    2. KOBIS 서비스 점검 중인지 확인해 주세요.
    """)
    st.stop()

# 5. API 응답 에러 체크 (KOBIS는 인증 실패 시에도 HTTP 200과 함께 faultInfo를 반환함)
if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 오류")
    st.error(f"⚠️ KOBIS API 오류 발생: {fault_msg}")
    st.info("""
    **확인해 주세요:**
    1. `KOBIS_KEY` 값이 정확하게 입력되었는지 확인해 주세요.
    2. KOBIS 공식 홈페이지에서 인증키가 활성화 상태인지 확인해 주세요.
    """)
    st.stop()

# 6. 영화 목록 데이터 추출
boxoffice_result = data.get("boxOfficeResult", {})
movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

if not movie_list:
    st.warning("📂 집계된 박스오피스 데이터가 없습니다.")
    st.info("""
    **확인해 주세요:**
    1. 해당 날짜의 데이터 집계가 아직 완료되지 않았을 수 있습니다.
    2. KOBIS 데이터 업데이트 시간을 확인해 주세요.
    """)
    st.stop()

# 7. 데이터 프레임 변환 및 전처리 (문자열 -> 숫자 변환)
df = pd.DataFrame(movie_list)

# 숫자로 변환할 컬럼 리스트
num_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# 8. 1위 영화 지표 카드 (Metric) 3장 표시
top_1 = df.iloc[0]

st.subheader(f"🥇 1위: {top_1['movieNm']}")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="일일 관객수",
        value=f"{int(top_1['audiCnt']):,} 명"
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{int(top_1['audiAcc']):,} 명"
    )

with col3:
    st.metric(
        label="상영 스크린수",
        value=f"{int(top_1['scrnCnt']):,} 개"
    )

st.divider()

# 9. 상위 5개 영화 일일 관객수 막대그래프
st.subheader("📊 관객수 TOP 5")
top_5_df = df.head(5).copy()

# 시각화를 위한 컬럼명 변경
chart_data = top_5_df.set_index("movieNm")[["audiCnt"]]
chart_data.columns = ["일일 관객수"]

st.bar_chart(chart_data)

st.divider()

# 10. 전체 순위 표 출력
st.subheader("📋 전체 박스오피스 순위")

# 필요한 컬럼만 추출하고 이름 변경
display_df = df[[
    "rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"
]].copy()

display_df.columns = [
    "순위", "영화명", "개봉일", "관객수(명)", "누적관객(명)", "스크린수(개)"
]

# 데이터 프레임 출력 (숫자 포맷팅 적용)
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(format="%d위"),
        "관객수(명)": st.column_config.NumberColumn(format="%d 명"),
        "누적관객(명)": st.column_config.NumberColumn(format="%d 명"),
        "스크린수(개)":
