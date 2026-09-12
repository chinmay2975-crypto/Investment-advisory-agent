import httpx
import streamlit as st

API_BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="InvestAd (Test Console)", layout="wide")


def api_get(path: str, **kwargs):
    try:
        response = httpx.get(f"{API_BASE_URL}{path}", timeout=30.0, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        st.error(f"GET {path} -> {exc.response.status_code}: {exc.response.text}")
    except httpx.HTTPError as exc:
        st.error(f"GET {path} failed: {exc}")
    return None


def api_post(path: str, **kwargs):
    try:
        response = httpx.post(f"{API_BASE_URL}{path}", timeout=60.0, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        st.error(f"POST {path} -> {exc.response.status_code}: {exc.response.text}")
    except httpx.HTTPError as exc:
        st.error(f"POST {path} failed: {exc}")
    return None


def api_put(path: str, **kwargs):
    try:
        response = httpx.put(f"{API_BASE_URL}{path}", timeout=30.0, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        st.error(f"PUT {path} -> {exc.response.status_code}: {exc.response.text}")
    except httpx.HTTPError as exc:
        st.error(f"PUT {path} failed: {exc}")
    return None


st.session_state.setdefault("investor_id", None)
st.session_state.setdefault("goal_id", None)

st.sidebar.title("InvestAd — Test Console")
page = st.sidebar.radio("Navigate", ["Investor & Profile", "Goals", "Market Intelligence", "Recommendations"])

st.sidebar.divider()
st.sidebar.caption("Current session")
st.sidebar.write(f"Investor ID: `{st.session_state.investor_id}`")
st.sidebar.write(f"Goal ID: `{st.session_state.goal_id}`")

try:
    httpx.get(f"{API_BASE_URL}/health", timeout=3.0).raise_for_status()
    st.sidebar.success("Backend reachable")
except httpx.HTTPError:
    st.sidebar.error(f"Backend unreachable at {API_BASE_URL}")

st.title(page)


if page == "Investor & Profile":
    st.subheader("Create a new investor")
    with st.form("create_investor"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        full_name = st.text_input("Full name (optional)")
        submitted = st.form_submit_button("Create investor")

    if submitted:
        result = api_post(
            "/investors/",
            json={"email": email, "password": password, "full_name": full_name or None},
        )
        if result:
            st.session_state.investor_id = result["id"]
            st.success(f"Created investor #{result['id']}")
            st.json(result)

    st.divider()
    st.subheader("Or use an existing investor ID")
    manual_id = st.number_input("Investor ID", min_value=1, step=1, value=st.session_state.investor_id or 1)
    if st.button("Load investor"):
        result = api_get(f"/investors/{manual_id}")
        if result:
            st.session_state.investor_id = result["id"]
            st.success(f"Loaded investor #{result['id']}")
            st.json(result)

    if st.session_state.investor_id:
        st.divider()
        st.subheader(f"Profile for investor #{st.session_state.investor_id}")

        with st.form("upsert_profile"):
            risk_cadence = st.selectbox("Risk cadence", ["Conservative", "Balanced", "Aggressive"])
            horizon_years = st.number_input("Horizon (years)", min_value=0, step=1, value=10)
            profile_submitted = st.form_submit_button("Save profile")

        if profile_submitted:
            result = api_put(
                f"/investors/{st.session_state.investor_id}/profile",
                json={"risk_cadence": risk_cadence, "horizon_years": int(horizon_years)},
            )
            if result:
                st.success("Profile saved")
                st.json(result)

        if st.button("Show allocation template"):
            result = api_get(f"/investors/{st.session_state.investor_id}/profile/allocation-template")
            if result:
                st.bar_chart(result)
                with st.expander("Raw response"):
                    st.json(result)


elif page == "Goals":
    if not st.session_state.investor_id:
        st.warning("Set an investor first on the 'Investor & Profile' page.")
    else:
        st.subheader(f"Create a goal for investor #{st.session_state.investor_id}")

        with st.form("create_goal"):
            category = st.text_input("Category", value="Retirement")
            target_amount = st.number_input("Target amount", min_value=0.0, value=50000.0, step=1000.0)
            current_amount = st.number_input("Current amount", min_value=0.0, value=5000.0, step=500.0)
            target_date = st.date_input("Target date")
            contribution_cadence = st.selectbox("Contribution cadence", ["monthly", "quarterly", "annually"])
            contribution_amount = st.number_input("Contribution amount", min_value=0.0, value=200.0, step=50.0)
            goal_submitted = st.form_submit_button("Create goal")

        if goal_submitted:
            result = api_post(
                f"/investors/{st.session_state.investor_id}/goals/",
                json={
                    "category": category,
                    "target_amount": target_amount,
                    "current_amount": current_amount,
                    "target_date": target_date.isoformat() + "T00:00:00",
                    "contribution_cadence": contribution_cadence,
                    "contribution_amount": contribution_amount,
                },
            )
            if result:
                st.session_state.goal_id = result["id"]
                st.success(f"Created goal #{result['id']}")
                st.json(result)

        st.divider()
        st.subheader("Existing goals")
        goals = api_get(f"/investors/{st.session_state.investor_id}/goals/")
        if goals:
            st.dataframe(
                [
                    {
                        "id": g["id"],
                        "category": g["category"],
                        "target_amount": g["target_amount"],
                        "current_amount": g["current_amount"],
                        "target_date": g["target_date"],
                    }
                    for g in goals
                ],
                use_container_width=True,
            )

            goal_ids = [g["id"] for g in goals]
            selected_goal_id = st.selectbox(
                "Select goal to analyze",
                goal_ids,
                index=goal_ids.index(st.session_state.goal_id) if st.session_state.goal_id in goal_ids else 0,
            )
            st.session_state.goal_id = selected_goal_id

            assumed_return = st.slider("Assumed annual return", 0.0, 0.20, 0.06, 0.01)
            if st.button("Analyze selected goal"):
                analysis = api_get(
                    f"/investors/{st.session_state.investor_id}/goals/{selected_goal_id}/analysis",
                    params={"assumed_annual_return": assumed_return},
                )
                if analysis:
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Required annual return", f"{analysis['required_annual_return']:.2%}")
                    col2.metric("Projected value", f"${analysis['projected_value']:,.2f}")
                    col3.metric("Sufficient?", "Yes" if analysis["is_sufficient"] else "No")
                    with st.expander("Raw response"):
                        st.json(analysis)
        else:
            st.info("No goals yet.")


elif page == "Market Intelligence":
    st.subheader("Refresh grounding data")
    if st.button("Run refresh pipeline"):
        result = api_post("/market-intelligence/refresh")
        if result:
            st.success(f"Ingested {result['documents_ingested']} documents")
            st.bar_chart(result["by_category"])
            with st.expander("Raw response"):
                st.json(result)

    st.divider()
    st.subheader("Query retrieved context")
    query_text = st.text_input("Query", value="inflation outlook")
    n_results = st.slider("Number of results", 1, 10, 5)
    if st.button("Run query"):
        result = api_get("/market-intelligence/query", params={"q": query_text, "n_results": n_results})
        if result:
            for hit in result["results"]:
                meta = hit["metadata"]
                st.markdown(
                    f"**[{meta.get('category')}] {meta.get('source')}** "
                    f"— as of {meta.get('as_of')} (distance {hit['distance']:.3f})"
                )
                st.write(hit["text"])
                st.divider()


elif page == "Recommendations":
    if not st.session_state.investor_id or not st.session_state.goal_id:
        st.warning("Set an investor and select a goal first on the 'Investor & Profile' and 'Goals' pages.")
    else:
        st.subheader(
            f"Generate recommendation for investor #{st.session_state.investor_id}, "
            f"goal #{st.session_state.goal_id}"
        )

        if st.button("Generate recommendation"):
            result = api_post(
                f"/investors/{st.session_state.investor_id}/recommendations/",
                params={"goal_id": st.session_state.goal_id},
            )
            if result:
                payload = result["payload"]
                st.success(f"Generated via **{result['llm_provider']}**")

                st.markdown(f"**What:** {payload['what']}")
                st.bar_chart(payload["target_allocation"])
                st.write("**Suggested instruments:**", ", ".join(payload["suggested_instruments"]))
                st.markdown(f"**Why:** {payload['why']}")
                st.markdown(f"**Expected behavior:** {payload['expected_behavior']}")
                st.metric("Goal probability", f"{payload['goal_probability']:.0%}")
                st.write("**Risks:**")
                for risk in payload["risks"]:
                    st.write(f"- {risk}")

                with st.expander("Raw response"):
                    st.json(result)

        st.divider()
        st.subheader("Recommendation history")
        history = api_get(f"/investors/{st.session_state.investor_id}/recommendations/")
        if history:
            st.dataframe(
                [
                    {
                        "id": r["id"],
                        "goal_id": r["goal_id"],
                        "status": r["status"],
                        "provider": r["llm_provider"],
                        "generated_at": r["generated_at"],
                        "goal_probability": r["payload"].get("goal_probability"),
                    }
                    for r in history
                ],
                use_container_width=True,
            )
        else:
            st.info("No recommendations yet.")
