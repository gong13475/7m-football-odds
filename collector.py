import requests
import streamlit as st

URL = "https://1x2.7mkr.com/result_kr.shtml"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )
}


def test_page():

    try:
        response = requests.get(
            URL,
            params={
                "cid": "",
                "dt": "2026-10-02"
            },
            headers=headers,
            timeout=30
        )

        st.write("HTTP 상태:", response.status_code)
        st.write("페이지 크기:", len(response.text))

        st.write(
            "FC 아우크스부르크 포함:",
            "아우크스부르크" in response.text
        )

        st.write(
            "비교 포함:",
            "비교" in response.text
        )

        st.write(
            "result_kr 포함:",
            "result_kr" in response.text
        )

        with st.expander("받은 HTML 앞부분"):
            st.code(
                response.text[:10000],
                language="html"
            )

    except Exception as e:

        st.error(
            f"접속 오류: {e}"
        )


st.title("7M 연결 진단")

if st.button("페이지 테스트"):
    test_page()
