import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 페이지 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("KOBIS 일일 박스오피스 데이터를 보여 줍니다.")


# ---------------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------
# 배포 서버가 다른 나라의 시간대를 사용하더라도
# 한국 시간(KST)을 기준으로 날짜를 계산합니다.
KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)
yesterday = now_kst.date() - timedelta(days=1)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여 줄 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# 3. KOBIS API 호출 함수
# ---------------------------------------------------------
# 같은 날짜의 결과는 1시간 동안 저장해 두어
# 페이지를 다시 실행해도 API를 계속 호출하지 않습니다.
@st.cache_data(ttl=3600)
def get_box_office(target_dt):
    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 인증키를 코드에 직접 작성하지 않습니다.
    api_key = st.secrets.get("KOBIS_KEY")

    if not api_key:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 앱 설정에서 Secrets를 확인하세요."
            ),
            "data": None
        }

    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 발생한 경우
        response.raise_for_status()

        result = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                "다음 사항을 확인해 주세요.\n"
                "• 인터넷 연결 상태\n"
                "• KOBIS API 주소\n"
                "• KOBIS API 서버 상태\n"
                f"• 요청 오류: {e}"
            ),
            "data": None
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API에서 올바른 JSON 데이터를 받지 못했습니다.\n\n"
                "KOBIS API 서버 상태를 확인해 주세요."
            ),
            "data": None
        }

    # -----------------------------------------------------
    # 4. 인증키 오류 확인
    # -----------------------------------------------------
    # KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인합니다.
    if "faultInfo" in result:
        fault_info = result["faultInfo"]

        fault_message = fault_info.get(
            "message",
            "KOBIS API에서 오류가 발생했습니다."
        )

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류가 발생했습니다.\n\n"
                f"오류 내용: {fault_message}\n\n"
                "KOBIS_KEY가 올바른지 확인해 주세요."
            ),
            "data": None
        }

    # -----------------------------------------------------
    # 5. 박스오피스 데이터 확인
    # -----------------------------------------------------
    box_office_result = result.get("boxOfficeResult")

    if not box_office_result:
        return {
            "success": False,
            "message": (
                "박스오피스 결과를 찾을 수 없습니다.\n\n"
                "KOBIS API 응답 형식이나 API 상태를 확인해 주세요."
            ),
            "data": None
        }

    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{display_date}의 영화 목록이 없습니다.\n\n"
                "다음 사항을 확인해 주세요.\n"
                "• 조회 날짜가 올바른지 확인\n"
                "• 해당 날짜의 박스오피스 데이터가 집계되었는지 확인\n"
                "• KOBIS API 상태 확인"
            ),
            "data": None
        }

    return {
        "success": True,
        "message": "",
        "data": movie_list
    }


# ---------------------------------------------------------
# 6. API에서 데이터 가져오기
# ---------------------------------------------------------
result = get_box_office(target_date)


# ---------------------------------------------------------
# 7. API 오류가 있으면 안내 메시지 표시
# ---------------------------------------------------------
if not result["success"]:
    st.error(result["message"])
    st.stop()


# ---------------------------------------------------------
# 8. 데이터를 표 형태로 변환
# ---------------------------------------------------------
movies = pd.DataFrame(result["data"])


# ---------------------------------------------------------
# 9. 숫자 데이터를 실제 숫자로 변환
# ---------------------------------------------------------
# KOBIS API에서는 숫자도 문자열로 전달되므로
# 그래프와 정렬에 사용할 수 있도록 숫자로 변환합니다.
number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in number_columns:
    if column in movies.columns:
        movies[column] = pd.to_numeric(
            movies[column],
            errors="coerce"
        ).fillna(0).astype(int)


# 순위 기준으로 정렬
movies = movies.sort_values("rank")


# ---------------------------------------------------------
# 10. 조회 날짜 표시
# ---------------------------------------------------------
st.subheader(f"📅 {display_date} 박스오피스")

st.caption(
    "한국 시간 기준으로 어제의 데이터를 조회합니다. "
    "동일한 날짜의 데이터는 약 1시간 동안 캐시됩니다."
)


# ---------------------------------------------------------
# 11. 1위 영화의 지표 카드
# ---------------------------------------------------------
first_movie = movies.iloc[0]

st.subheader("🥇 1위 영화")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="영화명",
        value=first_movie["movieNm"]
    )

with col2:
    st.metric(
        label="관객수",
        value=f"{first_movie['audiCnt']:,}명"
    )

with col3:
    st.metric(
        label="누적 관객수",
        value=f"{first_movie['audiAcc']:,}명"
    )


# ---------------------------------------------------------
# 12. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5편")

top5 = (
    movies
    .sort_values("audiCnt", ascending=False)
    .head(5)
    .copy()
)

# 영화명을 인덱스로 설정하면 Streamlit 막대그래프에서
# 영화 이름을 축에 표시할 수 있습니다.
chart_data = top5.set_index("movieNm")[["audiCnt"]]

st.bar_chart(chart_data)


# ---------------------------------------------------------
# 13. 전체 영화 표
# ---------------------------------------------------------
st.subheader("🎞️ 전체 박스오피스")

# 사용자에게 보여 줄 열만 선택합니다.
table = movies[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 표의 열 이름을 한국어로 변경합니다.
table.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True
)
