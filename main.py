import datetime
import requests
import pandas as pd
import pytz
import streamlit as st
import altair as alt

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="🎬 시네마 박스오피스",
    page_icon="🍿",
    layout="wide"
)

# 2. 고대비 다크 테마 적용 (회색 글씨 -> 선명한 하얀색/밝은 톤으로 수정)
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #ffffff !important;
    }
    div[data-testid="stMetric"], .stCard {
        background-color: #1a1c23;
        border: 1px solid #4a5568;
        border-radius: 10px;
        padding: 15px;
    }
    h1, h2, h3 {
        color: #f1c40f !important;
    }
    /* 서브텍스트 및 캡션 글자색을 명확한 밝은색으로 고정 */
    .stCaption, p, span, label {
        color: #ffffff !important;
    }
    </style>
""", unsafe_allow_html=True)

# 3. 날짜 설정 (KST)
kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.datetime.now(kst)
yesterday_kst = (now_kst - datetime.timedelta(days=1)).date()

st.title("🍿 시네마 일별 박스오피스")

if "chart_height" not in st.session_state:
    st.session_state.chart_height = 350

selected_date = st.date_input(
    label="📅 조회할 날짜 선택",
    value=yesterday_kst,
    max_value=yesterday_kst,
    min_value=datetime.date(2003, 11, 11)
)

target_date_str = selected_date.strftime('%Y%m%d')
formatted_date_str = selected_date.strftime('%Y년 %m월 %d일')

st.caption(f"기준일: {formatted_date_str} (한국 시간)")

# 4. API 키 확인
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키가 설정되지 않았습니다.")
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 5. API 요청
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_date_str
}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException:
    st.error("📡 API 서버 통신 오류")
    st.stop()

if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 오류")
    st.error(f"⚠️ KOBIS API 오류: {fault_msg}")
    st.stop()

# 6. 목록 추출 및 검증
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

df["formatted_movie_name"] = df.apply(format_movie_name, axis=1)
df["rank_change"] = df["rankInten"].apply(format_rank_inten)

st.divider()

# 8. 1위 영화 상세 정보
top_1 = df.iloc[0]
top_1_cd = top_1["movieCd"]

info_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
info_params = {
    "key": api_key,
    "movieCd": top_1_cd
}

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
        if directors:
            director_name = ", ".join(directors)
        
        genre_list = [g["genreNm"] for g in info_data.get("genres", [])]
        if genre_list:
            genres = ", ".join(genre_list)
        
        show_tm = f"{info_data.get('showTm', '-')}분"
        
        audits = info_data.get("audits", [])
        if audits:
            watch_grade = audits[0]["watchGradeNm"]
        
        actor_list = [a["peopleNm"] for a in info_data.get("actors", [])[:5]]
        if actor_list:
            actors = ", ".join(actor_list)
except Exception:
    pass

st.subheader(f"🥇 오늘의 1위: {top_1['formatted_movie_name']}")

# 1위 카드 지표
col1, col2, col3 = st.columns(3)
with col1:
    v1 = f"{int(top_1['audiCnt']):,} 명"
    st.metric(label="일일 관객수", value=v1)
with col2:
    v2 = f"{int(top_1['audiAcc']):,} 명"
    st.metric(label="누적 관객수", value=v2)
with col3:
    v3 = f"{int(top_1['scrnCnt']):,} 개"
    st.metric(label="상영 스크린수", value=v3)

# 1위 영화 상세설명
st.markdown("### 🎬 1위 영화 상세 정보")
st.info(
    f"- **감독:** {director_name}\n"
    f"- **장르:** {genres}\n"
    f"- **상영시간:** {show_tm}\n"
    f"- **관람등급:** {watch_grade}\n"
    f"- **주요 출연진:** {actors}\n"
    f"- **개봉일:** {top_1['openDt']}"
)

st.divider()

# 9. 막대 그래프 (가로 텍스트 라벨 적용)
st.subheader("📊 관객수 TOP 5")
st.write("📐 **그래프 크기(높이) 조절:**")

b_col1, b_col2, b_col3, _ = st.columns([1, 1, 1, 5])
with b_col1:
    if st.button("작게 (200px)"):
        st.session_state.chart_height = 200
with b_col2:
    if st.button("보통 (350px)"):
        st.session_state.chart_height = 350
with b_col3:
    if st.button("크게 (500px)"):
        st.session_state.chart_height = 500

top_5_df = df.head(5).copy()

# Altair 차트를 사용하여 x축 제목 라벨이 가로(0도)로 똑바로 출력되도록 고정
chart = alt.Chart(top_5_df).mark_bar(color="#f1c40f").encode(
    x=alt.X('movieNm:N', title='영화명', sort=None, axis=alt.Axis(labelAngle=0)),
    y=alt.Y('audiCnt:Q', title='일일 관객수(명)'),
    tooltip=['movieNm', 'audiCnt']
).properties(
    height=st.session_state.chart_height
)

st.altair_chart(chart, use_container_width=True)

st.divider()

# 10. 전체 박스오피스 순위표 출력
st.subheader("📋 전체 박스오피스 순위")

cols_to_select = [
    "rank",
    "rank_change",
    "formatted_movie_name",
    "openDt",
    "audiCnt",
    "audiAcc",
    "scrnCnt"
]

display_df = df[cols_to_select].copy()

new_column_names = [
    "순위",
    "순위변동",
    "영화명",
    "개봉일",
    "관객수(명)",
    "누적관객(명)",
    "스크린수(개)"
]

display_df.columns = new_column_names

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(format="%d위"),
        "관객수(명)": st.column_config.NumberColumn(format="%d 명"),
        "누적관객(명)": st.column_config.NumberColumn(format="%d 명"),
        "스크린수(개)": st.column_config.NumberColumn(format="%d 개")
    }
)
