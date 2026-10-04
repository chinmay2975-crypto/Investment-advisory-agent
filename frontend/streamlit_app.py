import httpx
import streamlit as st

API_BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="InvestAd", page_icon="📈", layout="wide")

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp { background-color: #f6f8fb; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

STATUS_COLORS = {"pending": "#b45309", "approved": "#1d4ed8", "confirmed": "#047857"}
RISK_STYLE = {
    "conservative": ("🛡️", "#1d4ed8"),
    "balanced": ("⚖️", "#b45309"),
    "aggressive": ("🚀", "#b91c1c"),
}


def badge(text: str, color: str) -> str:
    return (
        f'<span style="background:{color}1a;color:{color};padding:3px 10px;'
        f'border-radius:999px;font-size:0.8rem;font-weight:700;letter-spacing:0.02em;">'
        f"{text.upper()}</span>"
    )


def status_badge(status: str) -> str:
    return badge(status, STATUS_COLORS.get(status, "#6b7280"))


# ---------------------------------------------------------------------------
# API client with token-refresh-on-401
# ---------------------------------------------------------------------------


def _with_auth_headers(kwargs: dict) -> dict:
    token = st.session_state.get("access_token")
    if token:
        headers = {"Authorization": f"Bearer {token}", **kwargs.get("headers", {})}
        kwargs["headers"] = headers
    return kwargs


def _try_refresh_access_token() -> bool:
    refresh_token = st.session_state.get("refresh_token")
    if not refresh_token:
        return False
    try:
        response = httpx.post(
            f"{API_BASE_URL}/auth/refresh", json={"refresh_token": refresh_token}, timeout=10.0
        )
        response.raise_for_status()
    except httpx.HTTPError:
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        return False
    st.session_state.access_token = response.json()["access_token"]
    return True


def _request(method: str, path: str, **kwargs):
    call = getattr(httpx, method)
    timeout = kwargs.pop("timeout", 30.0)
    try:
        response = call(f"{API_BASE_URL}{path}", timeout=timeout, **_with_auth_headers(kwargs))
        if response.status_code == 401 and _try_refresh_access_token():
            response = call(f"{API_BASE_URL}{path}", timeout=timeout, **_with_auth_headers(kwargs))
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        st.error(f"{method.upper()} {path} -> {exc.response.status_code}: {exc.response.text}")
    except httpx.HTTPError as exc:
        st.error(f"{method.upper()} {path} failed: {exc}")
    return None


def api_get(path: str, **kwargs):
    return _request("get", path, **kwargs)


def api_post(path: str, **kwargs):
    kwargs.setdefault("timeout", 60.0)
    return _request("post", path, **kwargs)


def api_put(path: str, **kwargs):
    return _request("put", path, **kwargs)


def render_recommendation(result: dict):
    payload = result["payload"]
    st.caption(f"Generated via **{result['llm_provider']}**")

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


def _goto(page_name: str, **session_updates):
    st.session_state["_navigate_to"] = page_name
    for key, value in session_updates.items():
        st.session_state[key] = value
    st.rerun()


# ---------------------------------------------------------------------------
# Session state + navigation
# ---------------------------------------------------------------------------

st.session_state.setdefault("investor_id", None)
st.session_state.setdefault("goal_id", None)
st.session_state.setdefault("current_recommendation_id", None)
st.session_state.setdefault("access_token", None)
st.session_state.setdefault("refresh_token", None)

PAGES = [
    "Dashboard",
    "Investor & Profile",
    "Goals",
    "Portfolio",
    "Tax Analysis",
    "Market Intelligence",
    "Recommendations",
    "Refinement",
    "Scenarios",
    "Self-Assessment",
]
PAGE_ICONS = {
    "Dashboard": "🏠",
    "Investor & Profile": "👤",
    "Goals": "🎯",
    "Portfolio": "💼",
    "Tax Analysis": "🧾",
    "Market Intelligence": "🌐",
    "Recommendations": "🤖",
    "Refinement": "💬",
    "Scenarios": "📊",
    "Self-Assessment": "🔁",
}

st.session_state.setdefault("nav_page", "Investor & Profile")
if "_navigate_to" in st.session_state:
    st.session_state["nav_page"] = st.session_state.pop("_navigate_to")

with st.sidebar:
    st.markdown("## 📈 InvestAd")
    page = st.radio(
        "Navigate",
        PAGES,
        key="nav_page",
        format_func=lambda p: f"{PAGE_ICONS.get(p, '')}  {p}",
        label_visibility="collapsed",
    )

    st.divider()
    if st.session_state.access_token:
        with st.container(border=True):
            st.markdown(f"✅ **Logged in**  \nInvestor `#{st.session_state.investor_id}`")
            if st.session_state.goal_id:
                st.caption(f"Active goal: #{st.session_state.goal_id}")
            if st.button("Log out", use_container_width=True):
                st.session_state.access_token = None
                st.session_state.refresh_token = None
                st.session_state.investor_id = None
                st.rerun()
    else:
        st.warning("Not logged in")

    try:
        httpx.get(f"{API_BASE_URL}/health", timeout=3.0).raise_for_status()
        st.caption("🟢 Backend reachable")
    except httpx.HTTPError:
        st.caption(f"🔴 Backend unreachable at {API_BASE_URL}")

st.title(f"{PAGE_ICONS.get(page, '')} {page}")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

if page == "Dashboard":
    if not (st.session_state.investor_id and st.session_state.access_token):
        st.warning("Log in first on the 'Investor & Profile' page.")
    else:
        investor_id = st.session_state.investor_id

        profile = api_get(f"/investors/{investor_id}/profile")
        header_col1, header_col2 = st.columns([3, 1])
        with header_col1:
            st.subheader(f"Welcome back, investor #{investor_id}")
        with header_col2:
            if profile:
                st.metric("Risk cadence", profile["risk_cadence"])

        if not profile:
            with st.container(border=True):
                st.info("No investor profile set up yet.")
                if st.button("Set up profile →"):
                    _goto("Investor & Profile")

        with st.container(border=True):
            st.markdown("### 🎯 Goals")
            goals = api_get(f"/investors/{investor_id}/goals/")
            if not goals:
                st.info("No goals yet.")
                if st.button("Create a goal →"):
                    _goto("Goals")
            else:
                for goal in goals:
                    progress = 0.0
                    if goal["target_amount"]:
                        progress = min(goal["current_amount"] / goal["target_amount"], 1.0)
                    st.write(
                        f"**{goal['category']}** — ${goal['current_amount']:,.0f} of "
                        f"${goal['target_amount']:,.0f} (target {goal['target_date'][:10]})"
                    )
                    st.progress(progress)

                goal_ids = [g["id"] for g in goals]
                if st.session_state.goal_id not in goal_ids:
                    st.session_state.goal_id = goal_ids[0]
                selected_goal_id = st.selectbox(
                    "Primary goal for the sections below",
                    goal_ids,
                    index=goal_ids.index(st.session_state.goal_id),
                )
                st.session_state.goal_id = selected_goal_id

                analysis = api_get(f"/investors/{investor_id}/goals/{selected_goal_id}/analysis")
                if analysis:
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Required annual return", f"{analysis['required_annual_return']:.2%}")
                    col2.metric("Projected value", f"${analysis['projected_value']:,.2f}")
                    col3.metric("On track?", "Yes" if analysis["is_sufficient"] else "No")

        with st.container(border=True):
            st.markdown("### 💼 Portfolio")
            holdings = api_get(f"/investors/{investor_id}/holdings/")
            if not holdings:
                st.info("No holdings yet.")
                if st.button("Add holdings →"):
                    _goto("Portfolio")
            else:
                portfolio_analysis = api_get(f"/investors/{investor_id}/holdings/analysis")
                if portfolio_analysis:
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total market value", f"${portfolio_analysis['total_market_value']:,.2f}")
                    col2.metric(
                        "Unrealized gain/loss", f"${portfolio_analysis['unrealized_gain_loss']:,.2f}"
                    )
                    col3.metric("Risk profile", portfolio_analysis["risk_profile"])

                    chart_col1, chart_col2 = st.columns(2)
                    with chart_col1:
                        if portfolio_analysis["asset_allocation"]:
                            st.write("**Asset allocation**")
                            st.bar_chart(portfolio_analysis["asset_allocation"])
                    with chart_col2:
                        if portfolio_analysis["sector_exposure"]:
                            st.write("**Sector exposure**")
                            st.bar_chart(portfolio_analysis["sector_exposure"])

        with st.container(border=True):
            st.markdown("### 🤖 Latest recommendation")
            recommendations = api_get(f"/investors/{investor_id}/recommendations/")
            if not recommendations:
                st.info("No recommendations yet.")
                if st.button("Generate a recommendation →"):
                    _goto("Recommendations")
            else:
                latest = max(recommendations, key=lambda r: r["generated_at"])
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{latest['payload']['what']}**")
                    st.markdown(
                        f"{status_badge(latest['status'])} &nbsp; via {latest['llm_provider']}",
                        unsafe_allow_html=True,
                    )
                with col2:
                    st.metric("Goal probability", f"{latest['payload']['goal_probability']:.0%}")

                action_col1, action_col2 = st.columns(2)
                with action_col1:
                    if st.button("View & refine", use_container_width=True):
                        _goto("Refinement", current_recommendation_id=latest["id"])
                with action_col2:
                    if st.button("Compare scenarios", use_container_width=True):
                        _goto("Scenarios")


# ---------------------------------------------------------------------------
# Investor & Profile (auth + profile setup)
# ---------------------------------------------------------------------------

elif page == "Investor & Profile":
    if not (st.session_state.investor_id and st.session_state.access_token):
        _, center, _ = st.columns([1, 2, 1])
        with center:
            with st.container(border=True):
                login_tab, signup_tab = st.tabs(["Log in", "Sign up"])

                with login_tab:
                    with st.form("login_form"):
                        login_email = st.text_input("Email", key="login_email")
                        login_password = st.text_input(
                            "Password", type="password", key="login_password"
                        )
                        login_submitted = st.form_submit_button("Log in", use_container_width=True)

                    if login_submitted:
                        login_result = api_post(
                            "/auth/login", data={"username": login_email, "password": login_password}
                        )
                        if login_result:
                            st.session_state.access_token = login_result["access_token"]
                            st.session_state.refresh_token = login_result["refresh_token"]
                            st.session_state.investor_id = login_result["investor_id"]
                            _goto("Dashboard")

                with signup_tab:
                    with st.form("create_investor"):
                        email = st.text_input("Email", key="signup_email")
                        password = st.text_input("Password", type="password", key="signup_password")
                        full_name = st.text_input("Full name (optional)", key="signup_full_name")
                        submitted = st.form_submit_button("Create account", use_container_width=True)

                    if submitted:
                        result = api_post(
                            "/investors/",
                            json={"email": email, "password": password, "full_name": full_name or None},
                        )
                        if result:
                            login_result = api_post(
                                "/auth/login", data={"username": email, "password": password}
                            )
                            if login_result:
                                st.session_state.access_token = login_result["access_token"]
                                st.session_state.refresh_token = login_result["refresh_token"]
                                st.session_state.investor_id = login_result["investor_id"]
                                st.rerun()
    else:
        st.subheader(f"Profile for investor #{st.session_state.investor_id}")

        with st.container(border=True):
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

            if st.button("Show allocation template"):
                result = api_get(f"/investors/{st.session_state.investor_id}/profile/allocation-template")
                if result:
                    st.bar_chart(result)


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

elif page == "Goals":
    if not st.session_state.investor_id:
        st.warning("Log in first on the 'Investor & Profile' page.")
    else:
        with st.container(border=True):
            st.markdown("#### Create a goal")
            with st.form("create_goal"):
                category = st.text_input("Category", value="Retirement")
                target_amount = st.number_input("Target amount", min_value=0.0, value=50000.0, step=1000.0)
                current_amount = st.number_input("Current amount", min_value=0.0, value=5000.0, step=500.0)
                target_date = st.date_input("Target date")
                contribution_cadence = st.selectbox(
                    "Contribution cadence", ["monthly", "quarterly", "annually"]
                )
                contribution_amount = st.number_input(
                    "Contribution amount", min_value=0.0, value=200.0, step=50.0
                )
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

        st.markdown("#### Your goals")
        goals = api_get(f"/investors/{st.session_state.investor_id}/goals/")
        if goals:
            for goal in goals:
                progress = min(goal["current_amount"] / goal["target_amount"], 1.0) if goal["target_amount"] else 0.0
                with st.container(border=True):
                    st.markdown(f"**{goal['category']}** — target {goal['target_date'][:10]}")
                    st.progress(progress)
                    st.caption(f"${goal['current_amount']:,.0f} of ${goal['target_amount']:,.0f}")

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
        else:
            st.info("No goals yet.")


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

elif page == "Portfolio":
    if not st.session_state.investor_id:
        st.warning("Log in first on the 'Investor & Profile' page.")
    else:
        investor_id = st.session_state.investor_id

        col_add, col_upload = st.columns(2)
        with col_add:
            with st.container(border=True):
                st.markdown("#### Add a holding")
                with st.form("add_holding"):
                    ticker = st.text_input("Ticker", value="VTI")
                    quantity = st.number_input("Quantity", min_value=0.0, value=10.0, step=1.0)
                    cost_basis = st.number_input(
                        "Cost basis per share (optional)", min_value=0.0, value=0.0, step=1.0
                    )
                    add_submitted = st.form_submit_button("Add holding")

                if add_submitted:
                    result = api_post(
                        f"/investors/{investor_id}/holdings/",
                        json={"ticker": ticker, "quantity": quantity, "cost_basis": cost_basis or None},
                    )
                    if result:
                        st.success(f"Added holding #{result['id']}")

        with col_upload:
            with st.container(border=True):
                st.markdown("#### Or upload a CSV")
                st.caption("Columns: ticker, quantity, cost_basis")
                uploaded = st.file_uploader("Holdings CSV", type="csv", label_visibility="collapsed")
                if uploaded is not None and st.button("Upload CSV"):
                    result = api_post(
                        f"/investors/{investor_id}/holdings/csv-upload",
                        files={"file": (uploaded.name, uploaded.getvalue(), "text/csv")},
                    )
                    if result:
                        st.success(f"Uploaded {len(result)} holdings")

        st.markdown("#### Current holdings")
        holdings = api_get(f"/investors/{investor_id}/holdings/")
        if holdings:
            st.dataframe(holdings, use_container_width=True)
        else:
            st.info("No holdings yet.")

        st.markdown("#### Portfolio analysis")
        if st.button("Run analysis", type="primary"):
            analysis = api_get(f"/investors/{investor_id}/holdings/analysis")
            if analysis:
                with st.container(border=True):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total market value", f"${analysis['total_market_value']:,.2f}")
                    col2.metric("Unrealized gain/loss", f"${analysis['unrealized_gain_loss']:,.2f}")
                    col3.metric("Risk profile", analysis["risk_profile"])

                    chart_col1, chart_col2 = st.columns(2)
                    with chart_col1:
                        if analysis["asset_allocation"]:
                            st.write("**Asset allocation**")
                            st.bar_chart(analysis["asset_allocation"])
                    with chart_col2:
                        if analysis["sector_exposure"]:
                            st.write("**Sector exposure**")
                            st.bar_chart(analysis["sector_exposure"])


# ---------------------------------------------------------------------------
# Tax Analysis
# ---------------------------------------------------------------------------

elif page == "Tax Analysis":
    if not st.session_state.investor_id:
        st.warning("Log in first on the 'Investor & Profile' page.")
    else:
        investor_id = st.session_state.investor_id
        st.caption("Simplified, deterministic estimate — not tax advice.")

        with st.container(border=True):
            with st.form("tax_analysis_form"):
                ordinary_income_tax_rate = st.slider("Ordinary income tax rate", 0.0, 0.50, 0.24, 0.01)
                taxable_income = st.number_input(
                    "Taxable income (for long-term rate bracket)",
                    min_value=0.0,
                    value=100000.0,
                    step=5000.0,
                )
                filing_status = st.selectbox("Filing status", ["single", "married_filing_jointly"])
                tax_submitted = st.form_submit_button("Run tax analysis")

            if tax_submitted:
                result = api_post(
                    f"/investors/{investor_id}/holdings/tax-analysis",
                    json={
                        "ordinary_income_tax_rate": ordinary_income_tax_rate,
                        "taxable_income": taxable_income,
                        "filing_status": filing_status,
                    },
                )
                if result:
                    col1, col2 = st.columns(2)
                    col1.metric("Total unrealized gain", f"${result['total_unrealized_gain']:,.2f}")
                    col2.metric("Total estimated tax", f"${result['total_estimated_tax']:,.2f}")
                    st.dataframe(result["holdings"], use_container_width=True)


# ---------------------------------------------------------------------------
# Market Intelligence
# ---------------------------------------------------------------------------

elif page == "Market Intelligence":
    with st.container(border=True):
        st.markdown("#### Refresh grounding data")
        if st.button("Run refresh pipeline", type="primary"):
            result = api_post("/market-intelligence/refresh")
            if result:
                st.success(f"Ingested {result['documents_ingested']} documents")
                st.bar_chart(result["by_category"])

    with st.container(border=True):
        st.markdown("#### Query retrieved context")
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


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

elif page == "Recommendations":
    if not st.session_state.investor_id or not st.session_state.goal_id:
        st.warning("Log in and select a goal first (Investor & Profile → Goals).")
    else:
        if st.button("✨ Generate recommendation", type="primary"):
            result = api_post(
                f"/investors/{st.session_state.investor_id}/recommendations/",
                params={"goal_id": st.session_state.goal_id},
            )
            if result:
                st.session_state.current_recommendation_id = result["id"]
                with st.container(border=True):
                    render_recommendation(result)

        st.markdown("#### History")
        history = api_get(f"/investors/{st.session_state.investor_id}/recommendations/")
        if history:
            for r in sorted(history, key=lambda x: x["generated_at"], reverse=True):
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**#{r['id']}** — {r['payload']['what']}")
                        st.markdown(
                            f"{status_badge(r['status'])} &nbsp; {r['generated_at'][:16]} &nbsp; "
                            f"via {r['llm_provider']}",
                            unsafe_allow_html=True,
                        )
                    with col2:
                        st.metric("Goal prob.", f"{r['payload'].get('goal_probability', 0):.0%}")

            st.markdown("#### Approval & export")
            rec_ids = [r["id"] for r in history]
            selected_rec_id = st.selectbox("Recommendation", rec_ids, index=len(rec_ids) - 1)
            selected_rec = next(r for r in history if r["id"] == selected_rec_id)
            st.markdown(f"Current status: {status_badge(selected_rec['status'])}", unsafe_allow_html=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Approve", disabled=selected_rec["status"] != "pending", use_container_width=True):
                    result = api_post(
                        f"/investors/{st.session_state.investor_id}/recommendations/{selected_rec_id}/approve"
                    )
                    if result:
                        st.success("Approved")
                        st.rerun()
            with col2:
                if st.button(
                    "Confirm", disabled=selected_rec["status"] != "approved", use_container_width=True
                ):
                    result = api_post(
                        f"/investors/{st.session_state.investor_id}/recommendations/{selected_rec_id}/confirm"
                    )
                    if result:
                        st.success("Confirmed")
                        st.rerun()
            with col3:
                try:
                    pdf_path = (
                        f"/investors/{st.session_state.investor_id}"
                        f"/recommendations/{selected_rec_id}/export-pdf"
                    )
                    pdf_response = httpx.get(
                        f"{API_BASE_URL}{pdf_path}", timeout=30.0, **_with_auth_headers({})
                    )
                    if pdf_response.status_code == 401 and _try_refresh_access_token():
                        pdf_response = httpx.get(
                            f"{API_BASE_URL}{pdf_path}", timeout=30.0, **_with_auth_headers({})
                        )
                    pdf_response.raise_for_status()
                    st.download_button(
                        "📄 Download PDF",
                        data=pdf_response.content,
                        file_name=f"investment-target-sheet-{selected_rec_id}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except httpx.HTTPError as exc:
                    st.error(f"PDF export failed: {exc}")
        else:
            st.info("No recommendations yet.")


# ---------------------------------------------------------------------------
# Refinement — chat interface
# ---------------------------------------------------------------------------

elif page == "Refinement":
    if not st.session_state.investor_id or not st.session_state.current_recommendation_id:
        st.warning(
            "Generate a recommendation first on the 'Recommendations' page — refinement always "
            "continues an existing recommendation."
        )
    else:
        investor_id = st.session_state.investor_id
        current_id = st.session_state.current_recommendation_id

        session = api_get(f"/investors/{investor_id}/recommendations/{current_id}/refinement-session")
        current_rec = api_get(f"/investors/{investor_id}/recommendations/{current_id}")

        st.caption(f"Refining recommendation #{current_id}")
        if session:
            with st.expander(f"Active constraints · {len(session['messages'])} turn(s) so far"):
                st.json(session["active_constraints"])

        chat_box = st.container(height=420, border=True)
        with chat_box:
            with st.chat_message("assistant"):
                if current_rec:
                    st.write(current_rec["payload"]["what"])
                    st.caption("Current recommendation — ask me to adjust it below.")

            if session:
                for msg in session["messages"]:
                    with st.chat_message("user"):
                        st.write(msg["user_message"])
                    with st.chat_message("assistant"):
                        resulting = api_get(
                            f"/investors/{investor_id}/recommendations/{msg['resulting_recommendation_id']}"
                        )
                        if resulting:
                            st.write(resulting["payload"]["what"])
                        st.caption(f"via {msg['llm_provider']}")

        message = st.chat_input("e.g. 'remove NVIDIA', 'more bonds'")
        if message:
            result = api_post(
                f"/investors/{investor_id}/recommendations/{current_id}/refine",
                json={"message": message},
            )
            if result:
                st.session_state.current_recommendation_id = result["id"]
                st.rerun()

        if current_rec:
            with st.expander("Full detail of the current recommendation"):
                render_recommendation(current_rec)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

elif page == "Scenarios":
    if not st.session_state.investor_id or not st.session_state.goal_id:
        st.warning("Log in and select a goal first (Investor & Profile → Goals).")
    else:
        investor_id = st.session_state.investor_id
        goal_id = st.session_state.goal_id

        if st.button("Run scenario comparison", type="primary"):
            result = api_post(f"/investors/{investor_id}/goals/{goal_id}/scenarios/")
            if result:
                st.session_state["_last_scenario_run"] = result

        result = st.session_state.get("_last_scenario_run")
        if result:
            cols = st.columns(3)
            for col, variant in zip(cols, ["conservative", "balanced", "aggressive"]):
                icon, color = RISK_STYLE[variant]
                with col:
                    with st.container(border=True):
                        st.markdown(
                            f"### {icon} {badge(variant, color)}", unsafe_allow_html=True
                        )
                        render_recommendation(result[f"{variant}_recommendation"])

        st.markdown("#### History")
        history = api_get(f"/investors/{investor_id}/goals/{goal_id}/scenarios/")
        if history:
            st.dataframe(
                [
                    {
                        "id": run["id"],
                        "created_at": run["created_at"],
                        "conservative_goal_probability": run["conservative_recommendation"]["payload"].get(
                            "goal_probability"
                        ),
                        "balanced_goal_probability": run["balanced_recommendation"]["payload"].get(
                            "goal_probability"
                        ),
                        "aggressive_goal_probability": run["aggressive_recommendation"]["payload"].get(
                            "goal_probability"
                        ),
                    }
                    for run in history
                ],
                use_container_width=True,
            )
        else:
            st.info("No scenario runs yet.")


# ---------------------------------------------------------------------------
# Self-Assessment
# ---------------------------------------------------------------------------

elif page == "Self-Assessment":
    if not st.session_state.investor_id:
        st.warning("Log in first on the 'Investor & Profile' page.")
    else:
        investor_id = st.session_state.investor_id
        st.caption("Checks how a past recommendation actually played out and logs a reflection for review.")

        history = api_get(f"/investors/{investor_id}/recommendations/")
        if not history:
            st.info("No recommendations yet for this investor.")
        else:
            rec_ids = [r["id"] for r in history]
            selected_rec_id = st.selectbox("Recommendation to evaluate", rec_ids, index=len(rec_ids) - 1)

            if st.button("Run self-assessment now", type="primary"):
                result = api_post(
                    f"/investors/{investor_id}/recommendations/{selected_rec_id}/evaluations/"
                )
                if result:
                    with st.container(border=True):
                        st.success("Evaluation complete")
                        st.metric("Assumptions held?", "Yes" if result["assumptions_held"] else "No")
                        if result["deviation"]:
                            st.write("**Deviation**")
                            st.json(result["deviation"])
                        st.write("**Contributing factors**")
                        st.write(result["contributing_factors"])

            st.markdown("#### Evaluation history")
            evaluations = api_get(f"/investors/{investor_id}/recommendations/{selected_rec_id}/evaluations/")
            if evaluations:
                for e in evaluations:
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.caption(f"Evaluation #{e['id']} · {e['evaluated_at'][:16]}")
                            st.write(e["contributing_factors"])
                        with col2:
                            st.metric("Held?", "Yes" if e["assumptions_held"] else "No")
                            st.caption(f"Deviation: {(e['deviation'] or {}).get('deviation_pct', '—')}")
                        with st.expander("Raw deviation"):
                            st.json(e["deviation"])
            else:
                st.info("No evaluations yet for this recommendation.")
