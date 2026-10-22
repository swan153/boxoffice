import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# 1. 페이지 기본 설정 (영화관 테마)
st.set_page_config(
    page_title="🎬 시네마 박스오피스",
    page_icon="🍿",
    layout="wide"
)

# 영화관 무드의 다크 테마 Custom CSS 적용
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #e0e0e0;
    }
    div[data-testid="stMetric"], .stCard {
        background-color: #1a1c23;
        border: 1px solid #333d4d;
        border-radius: 10px;
        padding: 15px;
    }
    h1, h2, h3 {
        color: #f39c12 !important;
    }
    .stCaption {
        color: #a0a0a0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# 2. 한국 표준시(KST) 기준 날짜 설정
kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.datetime.now(kst)
yesterday_kst = (now_kst - datetime.timedelta(days=1)).date()

# 헤더 타이틀
st.title("🍿 시네마 일별 박스오피스")

# 세션 상태 초기화 (그래프 높이 조절용)
if "chart_height" not in st.session_state:
    st.session_state.chart_height = 350

# 날짜 선택 (최대: 어제)
selected_date = st.date_input(
    label="📅 조회할 날짜를 선택하세요 (오늘 날짜는 아직 집계 전입니다)",
    value=yesterday_kst,
    max_value=yesterday_kst,
    min_value=datetime.date(2003, 11, 11)
)

target_date_str = selected_date.strftime('%Y%m%d')
formatted_date_str = selected_date.strftime('%Y년 %m월 %d일')

st.caption(f"기준일: {formatted_date_str} (한국 시간 기준)")

# 3. Streamlit Secrets에서 API 키 불러오기
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키가 설정되지 않았습니다.")
    st.info("Streamlit Cloud 설정의 Secrets에서 KOBIS_KEY를 지정해 주세요.")
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 4. 일별 박스오피스 API 데이터 요청
boxoffice_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_date_str
}

try:
    response = requests.get(boxoffice_url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException:
    st.error("📡 API 서버와의 통신 중 오류가 발생했습니다.")
    st.stop()

# 5. API 응답 에러 체크 (faultInfo)
if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 오류")
    st.error(f"⚠️ KOBIS API 오류 발생: {fault_msg}")
    st.stop()

# 6. 영화 목록 추출 및 비어있을 때 예외 처리
boxoffice_result = data.get("boxOfficeResult", {})
movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

if not movie_list:
    st.warning("📂 그날은 아직 집계 전입니다.")
    st.stop()

# 7. 데이터 전처리
df = pd.DataFrame(movie_list)
num_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# 전처리 함수 정의
def format_movie_name(row):
    if row["audiAcc"] >= 1_000_000:
        return f"{row['movieNm']} 🏆"
    return row["movieNm"]

def format_rank_inten(inten):
    inten = int(inten)
    if inten > 0:
        return f"🔺 {inten}"
    elif inten < 0:
        return f"🔹 {abs(inten)}"
    return "-"

# 데이터 가공 (잘림 방지를 위해 간결하게 작성)
df["formatted_movie_name"] = df.apply(format_movie_name, axis=1)
df["rank_change"] = df["rankInten"].apply(format_rank_inten)

st.divider()

# 8. 1위 영화 상세 정보 API 추가 요청 및 표시
top_1 = df.iloc[0]
top_1_cd = top_1["movieCd"]

info_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
info_params = {"key": api_key, "movieCd": top_1_cd}

director_name = "정보 없음"
genres = "정보 없음"
show_tm = "-"
watch_grade = "정보 없음"
actors = "정보 없음"

try:
    info_res = requests.get(info_url, params=info_params, timeout=5)
    if info_res.status_code == 200:
        info_data = info_res.json().get("movieInfoResult", {}).get("movieInfo", {})
        
        directors = [d["peopleNm"] for d in info_data.get("directors", [])]
        director_name = ", ".join(directors) if directors else "정보 없음"
        
        genre_list = [g["genreNm"] for g in info_data.get("genres", [])]
        genres = ", ".join(genre_list) if genre_list else "정보 없음"
        
        show_tm = f"{info_data.get('showTm', '-')}분"
        
        audits = info_data.get("audits", [])
        watch_grade = audits[0]["watchGradeNm"] if audits else "정보 없음"
        
        actor_list = [a["peopleNm"] for a in info_data.get("actors", [])[:5]]
        actors = ", ".join(actor_list) if actor_list else "정보 없음"
except Exception:
    pass

st.subheader(f"🥇 오늘의 1위 영화: {top_1['formatted_movie_name']}")

# 1위 영화 지표 카드 3개
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="일일 관
