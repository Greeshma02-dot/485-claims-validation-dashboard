import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="485 Claims Validation",
    page_icon="📊",
    layout="wide"
)


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = (
    BASE_DIR
    / "deploy_data"
    / "claims_dashboard_public_safe.parquet"
)

CLAIMS_SNAPSHOT_DATE = pd.Timestamp(
    "2026-08-28"
)


# =========================================================
# LOAD DATA
# =========================================================

@st.cache_data
def load_dashboard_data():

    if not DATA_FILE.exists():
        return None

    data = pd.read_parquet(
        DATA_FILE
    )

    date_columns = [
        "Date Parsed",
        "Final HHA Stop Date",
        "TAH HHA Stop Date",
        "First Any TAH Service Date",
        "First TAH Service Date"
    ]

    for column in date_columns:

        if column in data.columns:

            data[column] = pd.to_datetime(
                data[column],
                errors="coerce"
            )

    return data


df = load_dashboard_data()


if df is None:

    st.error(
        "claims_dashboard_data.parquet was not found. "
        "Run build_final_claims_master.py first."
    )

    st.stop()


# =========================================================
# DISPLAY HELPERS
# =========================================================

def mask_mbi(value):

    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value == "":
        return ""

    if len(value) <= 4:
        return "*" * len(value)

    return (
        "*" * (len(value) - 4)
        + value[-4:]
    )



# =========================================================
# REBECCA'S UPDATED CLAIMS TERMINOLOGY
#
# IMPORTANT:
# Backend validated field remains unchanged.
# We are only changing the user-facing wording.
# =========================================================

consistency_map = {

    "Claims Support Recommendation":
        "Claims Consistent with Recommendation",

    "Claims Do Not Support Recommendation":
        "Claims Not Consistent with Recommendation"
}


df[
    "Claims Consistency Status"
] = df[
    "Claims Alignment Status"
].replace(
    consistency_map
)


df[
    "Claims Consistency Reason"
] = df[
    "Claims Alignment Reason"
].fillna("")


# =========================================================
# TAH COVERAGE STATUS
# =========================================================

def get_tah_coverage_status(row):

    if (
        row["Recommendation Category"]
        !=
        "Transition to Therapy at Home"
    ):

        return "Not Applicable"

    aco = str(
        row["ACO Clean"]
    ).strip().upper()

    if aco in [
        "CCPACO",
        "NJPACO"
    ]:

        return "Source Available"

    if aco == "HORIZON":

        return (
            "Coverage Confirmation Needed"
        )

    return "Source Unavailable"


df[
    "TAH Coverage Status"
] = df.apply(
    get_tah_coverage_status,
    axis=1
)


# =========================================================
# TAH NOT APPLICABLE REASON
# =========================================================

def get_tah_not_applicable_reason(row):

    if (
        row["Recommendation Category"]
        !=
        "Transition to Therapy at Home"
    ):

        return ""

    if (
        row["TAH Result"]
        !=
        "Not Applicable"
    ):

        return ""

    hha_result = row[
        "Final HHA Result"
    ]

    if hha_result == "Continued":

        return (
            "HHA Continued - "
            "TAH sequencing not applicable"
        )

    if hha_result == "Restarted":

        return (
            "HHA Restarted - "
            "TAH sequencing not applicable"
        )

    if hha_result == "Excluded":

        return (
            "HHA Excluded / Confounded - "
            "TAH sequencing not applicable"
        )

    return (
        "TAH sequencing not applicable "
        "based on HHA result"
    )


df[
    "TAH Not Applicable Reason"
] = df.apply(
    get_tah_not_applicable_reason,
    axis=1
)


# =========================================================
# FINAL USER-FACING TAH REASON
# =========================================================

def get_display_tah_reason(row):

    if (
        row["TAH Result"]
        == "Not Applicable"
    ):

        return row[
            "TAH Not Applicable Reason"
        ]

    current_reason = row.get(
        "TAH Result Reason",
        ""
    )

    if pd.isna(current_reason):
        return ""

    return str(current_reason)


df[
    "TAH Result Reason Display"
] = df.apply(
    get_display_tah_reason,
    axis=1
)


# =========================================================
# HELPERS
# =========================================================

def determinate_alignment_rate(data):

    consistent = (
        data[
            "Claims Consistency Status"
        ]
        ==
        "Claims Consistent with Recommendation"
    ).sum()

    not_consistent = (
        data[
            "Claims Consistency Status"
        ]
        ==
        "Claims Not Consistent with Recommendation"
    ).sum()

    denominator = (
        consistent
        +
        not_consistent
    )

    if denominator == 0:

        return (
            0,
            consistent,
            not_consistent,
            denominator
        )

    return (
        consistent / denominator,
        consistent,
        not_consistent,
        denominator
    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title(
        "485 Claims Validation"
    )

    st.caption(
        "Claims snapshot: 08/28/2026"
    )

    st.divider()

    page = st.radio(
        "Dashboard Page",
        [
            "Executive Summary",
            "Claims Consistency",
            "Recommendation Detail",
            "QA & Validation"
        ]
    )

    st.divider()

    st.subheader(
        "Filters"
    )


    # ACO
    aco_values = sorted(
        [
            value
            for value
            in df[
                "ACO Clean"
            ].dropna().unique()
            if str(value).strip() != ""
        ]
    )

    selected_acos = st.multiselect(
        "ACO",
        aco_values
    )


    # PRACTICE
    practice_values = sorted(
        [
            value
            for value
            in df[
                "Practice Clean"
            ].dropna().unique()
            if str(value).strip() != ""
        ]
    )

    selected_practices = st.multiselect(
        "Practice",
        practice_values
    )


    # CATEGORY
    category_values = sorted(
        df[
            "Recommendation Category"
        ]
        .dropna()
        .unique()
    )

    selected_categories = st.multiselect(
        "Recommendation Category",
        category_values
    )


    # DATE
    minimum_date = (
        df[
            "Date Parsed"
        ]
        .min()
        .date()
    )

    maximum_date = (
        df[
            "Date Parsed"
        ]
        .max()
        .date()
    )

    selected_dates = st.date_input(
        "Recommendation Date",
        value=(
            minimum_date,
            maximum_date
        ),
        min_value=minimum_date,
        max_value=maximum_date
    )


# =========================================================
# GLOBAL FILTERS
# =========================================================

filtered = df.copy()


if selected_acos:

    filtered = filtered[
        filtered[
            "ACO Clean"
        ].isin(
            selected_acos
        )
    ]


if selected_practices:

    filtered = filtered[
        filtered[
            "Practice Clean"
        ].isin(
            selected_practices
        )
    ]


if selected_categories:

    filtered = filtered[
        filtered[
            "Recommendation Category"
        ].isin(
            selected_categories
        )
    ]


if (
    isinstance(
        selected_dates,
        tuple
    )
    and len(
        selected_dates
    ) == 2
):

    start_date = pd.Timestamp(
        selected_dates[0]
    )

    end_date = pd.Timestamp(
        selected_dates[1]
    )

    filtered = filtered[
        (
            filtered[
                "Date Parsed"
            ]
            >= start_date
        )
        &
        (
            filtered[
                "Date Parsed"
            ]
            <= end_date
        )
    ]


# =========================================================
# COMMON HEADER
# =========================================================

st.title(
    f"485 Claims Validation – {page}"
)


st.caption(
    "Claims-based validation of V1 485 recommendations. "
    "Practice acceptance or response is not captured in the "
    "source data; claims consistency reflects observed claims "
    "activity only."
)


# =========================================================
# EXECUTIVE SUMMARY
# =========================================================

if page == "Executive Summary":

    (
        current_rate,
        consistent,
        not_consistent,
        determinate_cases
    ) = determinate_alignment_rate(
        filtered
    )


    total_v1 = len(
        filtered
    )


    discharge_count = (
        filtered[
            "Recommendation Category"
        ]
        ==
        "Discharge from Home Health"
    ).sum()


    tah_count = (
        filtered[
            "Recommendation Category"
        ]
        ==
        "Transition to Therapy at Home"
    ).sum()


    c1, c2, c3, c4 = st.columns(
        4
    )


    with c1:

        st.metric(
            "Determinate Claims Alignment Rate",
            f"{current_rate:.2%}"
        )

        st.caption(
            f"{consistent:,} Consistent / "
            f"{determinate_cases:,} Determinate Cases"
        )


    with c2:

        st.metric(
            "V1 Recommendations",
            f"{total_v1:,}"
        )


    with c3:

        st.metric(
            "Discharge from HHA",
            f"{discharge_count:,}"
        )


    with c4:

        st.metric(
            "Therapy at Home Recommendations",
            f"{tah_count:,}"
        )


    st.divider()


    # =====================================================
    # HHA + TAH RESULTS
    # =====================================================

    left, right = st.columns(
        2
    )


    with left:

        st.subheader(
            "HHA Results"
        )


        hha_order = [
            "Pending",
            "Continued",
            "Stopped",
            "Unable to Match",
            "Excluded",
            "Restarted"
        ]


        hha_counts = (
            filtered[
                "Final HHA Result"
            ]
            .value_counts()
            .reindex(
                hha_order,
                fill_value=0
            )
            .reset_index()
        )


        hha_counts.columns = [
            "Final HHA Result",
            "Count"
        ]


        fig_hha = px.bar(
            hha_counts,
            x="Count",
            y="Final HHA Result",
            orientation="h",
            text="Count"
        )


        fig_hha.update_layout(
            showlegend=False,
            xaxis_title="",
            yaxis_title="",
            height=360
        )


        st.plotly_chart(
            fig_hha,
            use_container_width=True
        )


    with right:

        st.subheader(
            "Therapy at Home Results"
        )


        tah_only = filtered[
            filtered[
                "Recommendation Category"
            ]
            ==
            "Transition to Therapy at Home"
        ].copy()


        tah_counts = (
            tah_only[
                "TAH Result"
            ]
            .value_counts()
            .reset_index()
        )


        tah_counts.columns = [
            "TAH Result",
            "Count"
        ]


        if len(
            tah_counts
        ) > 0:

            fig_tah = px.pie(
                tah_counts,
                names="TAH Result",
                values="Count",
                hole=0.55
            )


            fig_tah.update_traces(
                textposition="outside",
                textinfo="value+percent"
            )


            fig_tah.update_layout(
                height=360
            )


            st.plotly_chart(
                fig_tah,
                use_container_width=True
            )


    # =====================================================
    # MATURITY + ACO
    # =====================================================

    left, right = st.columns(
        2
    )


    with left:

        st.subheader(
            "Claims Maturity Status"
        )


        maturity_order = [
            "Under 30 Days",
            "30-59 Days",
            "60-89 Days",
            "90-119 Days",
            "120+ Days"
        ]


        def maturity_bucket(days):

            if pd.isna(days):
                return "Unknown"

            if days < 30:
                return "Under 30 Days"

            if days < 60:
                return "30-59 Days"

            if days < 90:
                return "60-89 Days"

            if days < 120:
                return "90-119 Days"

            return "120+ Days"


        maturity_data = filtered.copy()


        maturity_data[
            "Maturity Bucket"
        ] = maturity_data[
            "Claims Maturity Days"
        ].apply(
            maturity_bucket
        )


        maturity_counts = (
            maturity_data[
                "Maturity Bucket"
            ]
            .value_counts()
            .reindex(
                maturity_order,
                fill_value=0
            )
            .reset_index()
        )


        maturity_counts.columns = [
            "Maturity Status",
            "Count"
        ]


        fig_maturity = px.bar(
            maturity_counts,
            x="Count",
            y="Maturity Status",
            orientation="h",
            text="Count"
        )


        fig_maturity.update_layout(
            showlegend=False,
            xaxis_title="",
            yaxis_title="",
            height=350
        )


        st.plotly_chart(
            fig_maturity,
            use_container_width=True
        )


        st.caption(
            "Current methodology uses 90 days as the V1 "
            "working maturity threshold and 120 days as the "
            "extended review window. Future enhancement: "
            "affirmative claims evidence may support earlier "
            "determination when the expected claims pattern "
            "is already observable."
        )


    with right:

        st.subheader(
            "V1 Recommendations by ACO"
        )


        aco_counts = (
            filtered[
                "ACO Clean"
            ]
            .value_counts()
            .reset_index()
        )


        aco_counts.columns = [
            "ACO",
            "Count"
        ]


        fig_aco = px.bar(
            aco_counts,
            x="ACO",
            y="Count",
            text="Count"
        )


        fig_aco.update_layout(
            showlegend=False,
            xaxis_title="",
            yaxis_title="",
            height=350
        )


        st.plotly_chart(
            fig_aco,
            use_container_width=True
        )


    st.info(
        "Methodology note: Claims consistency reflects "
        "observed claims activity only. It does not establish "
        "that a practice accepted, rejected, or acted on the "
        "recommendation."
    )


# =========================================================
# CLAIMS CONSISTENCY
# =========================================================

elif page == "Claims Consistency":

    (
        rate,
        consistent,
        not_consistent,
        determinate
    ) = determinate_alignment_rate(
        filtered
    )


    pending = (
        filtered[
            "Claims Consistency Status"
        ]
        ==
        "Pending"
    ).sum()


    c1, c2, c3, c4 = st.columns(
        4
    )


    with c1:

        st.metric(
            "Claims Consistent",
            f"{consistent:,}"
        )


    with c2:

        st.metric(
            "Claims Not Consistent",
            f"{not_consistent:,}"
        )


    with c3:

        st.metric(
            "Claims Pending",
            f"{pending:,}"
        )


    with c4:

        st.metric(
            "Determinate Claims Alignment Rate",
            f"{rate:.2%}"
        )

        st.caption(
            f"{consistent:,} / "
            f"{determinate:,} Determinate Cases"
        )


    st.divider()


    left, right = st.columns(
        [
            0.42,
            0.58
        ]
    )


    with left:

        st.subheader(
            "Are Claims Consistent with the Recommendation?"
        )


        alignment_order = [
            "Pending",
            "Claims Not Consistent with Recommendation",
            "Unable to Determine",
            "Claims Consistent with Recommendation",
            "Excluded / Confounded",
            "Restarted / Mixed Evidence"
        ]


        alignment_counts = (
            filtered[
                "Claims Consistency Status"
            ]
            .value_counts()
            .reindex(
                alignment_order,
                fill_value=0
            )
            .reset_index()
        )


        alignment_counts.columns = [
            "Claims Consistency Status",
            "Count"
        ]


        fig_alignment = px.bar(
            alignment_counts,
            x="Count",
            y="Claims Consistency Status",
            orientation="h",
            text="Count"
        )


        fig_alignment.update_layout(
            showlegend=False,
            xaxis_title="",
            yaxis_title="",
            height=440
        )


        st.plotly_chart(
            fig_alignment,
            use_container_width=True
        )


    with right:

        st.subheader(
            "Claims Consistency by ACO"
        )


        aco_alignment = (
            filtered
            .groupby(
                [
                    "ACO Clean",
                    "Claims Consistency Status"
                ]
            )
            .size()
            .reset_index(
                name="Count"
            )
        )


        fig_aco_alignment = px.bar(
            aco_alignment,
            x="Count",
            y="ACO Clean",
            color="Claims Consistency Status",
            orientation="h",
            barmode="stack"
        )


        fig_aco_alignment.update_layout(
            xaxis_title="",
            yaxis_title="",
            height=440
        )


        st.plotly_chart(
            fig_aco_alignment,
            use_container_width=True
        )


    st.subheader(
        "Claims Consistency by Recommendation Type"
    )


    category_alignment = (
        filtered
        .groupby(
            [
                "Recommendation Category",
                "Claims Consistency Status"
            ]
        )
        .size()
        .reset_index(
            name="Count"
        )
    )


    fig_category = px.bar(
        category_alignment,
        x="Count",
        y="Recommendation Category",
        color="Claims Consistency Status",
        orientation="h",
        barmode="stack"
    )


    fig_category.update_layout(
        xaxis_title="",
        yaxis_title="",
        height=360
    )


    st.plotly_chart(
        fig_category,
        use_container_width=True
    )


    st.info(
        '"Claims Consistent with Recommendation" means '
        "the observed claims pattern is consistent with the "
        "recommendation. It does not establish that the "
        "practice accepted or acted on the recommendation."
    )


# =========================================================
# RECOMMENDATION DETAIL
# =========================================================

elif page == "Recommendation Detail":

    detail = filtered.copy()


    d1, d2 = st.columns(
        2
    )


    with d1:

        selected_hha = st.multiselect(
            "Final HHA Result",
            sorted(
                detail[
                    "Final HHA Result"
                ]
                .dropna()
                .unique()
            )
        )


    with d2:

        selected_tah = st.multiselect(
            "TAH Result",
            sorted(
                [
                    value
                    for value
                    in detail[
                        "TAH Result"
                    ].dropna().unique()
                    if str(value).strip() != ""
                ]
            )
        )


    if selected_hha:

        detail = detail[
            detail[
                "Final HHA Result"
            ].isin(
                selected_hha
            )
        ]


    if selected_tah:

        detail = detail[
            detail[
                "TAH Result"
            ].isin(
                selected_tah
            )
        ]


    st.metric(
        "Recommendations Displayed",
        f"{len(detail):,}"
    )


    detail_columns = [
        "Recommendation ID",
        "ACO Clean",
        "Practice Clean",
        "MBI Display",
        "Date Parsed",
        "Recommendation Category",
        "V1 Claims Scope",
        "Claims Maturity Status",
        "Final HHA Result",
        "Final Exclusion Reason",
        "Final HHA Stop Date",
        "TAH Result",
        "TAH Result Reason Display",
        "TAH Coverage Status",
        "TAH HHA Stop Date",
        "First TAH Service Date",
        "TAH Maturity Status",
        "Claims Consistency Status",
        "Claims Consistency Reason"
    ]


    detail_columns = [
        column
        for column in detail_columns
        if column in detail.columns
    ]


    display_detail = detail[
        detail_columns
    ].copy()


    display_detail = (
        display_detail.rename(
            columns={
                "ACO Clean":
                    "ACO",

                "Practice Clean":
                    "Practice",

                "MBI Display":
                    "MBI",

                "Date Parsed":
                    "Recommendation Date",

                "Final HHA Stop Date":
                    "HHA Stop Date",

                "TAH Result Reason Display":
                    "TAH Result Reason"
            }
        )
    )


    st.dataframe(
        display_detail,
        use_container_width=True,
        hide_index=True,
        height=650,

        column_config={

            "Recommendation Date":
                st.column_config.DateColumn(
                    "Recommendation Date",
                    format="MM/DD/YYYY"
                ),

            "HHA Stop Date":
                st.column_config.DateColumn(
                    "HHA Stop Date",
                    format="MM/DD/YYYY"
                ),

            "TAH HHA Stop Date":
                st.column_config.DateColumn(
                    "TAH HHA Stop Date",
                    format="MM/DD/YYYY"
                ),

            "First TAH Service Date":
                st.column_config.DateColumn(
                    "First TAH Service Date",
                    format="MM/DD/YYYY"
                )
        }
    )


# =========================================================
# QA & VALIDATION
# =========================================================

elif page == "QA & Validation":

    unique_id_pass = (
        filtered[
            "Recommendation ID"
        ]
        .duplicated()
        .sum()
        == 0
    )


    scope_pass = (
        len(filtered)
        ==
        (
            (
                filtered[
                    "Recommendation Category"
                ]
                ==
                "Discharge from Home Health"
            ).sum()
            +
            (
                filtered[
                    "Recommendation Category"
                ]
                ==
                "Transition to Therapy at Home"
            ).sum()
        )
    )


    hha_pass = (
        filtered[
            "Final HHA Result"
        ]
        .notna()
        .sum()
        ==
        len(filtered)
    )


    filtered_tah = filtered[
        filtered[
            "Recommendation Category"
        ]
        ==
        "Transition to Therapy at Home"
    ].copy()


    tah_pass = (
        filtered_tah[
            "TAH Result"
        ]
        .astype(str)
        .str.strip()
        .ne("")
        .sum()
        ==
        len(filtered_tah)
    )


    q1, q2, q3, q4 = st.columns(
        4
    )


    with q1:

        st.metric(
            "Unique Recommendation IDs",
            "PASS"
            if unique_id_pass
            else "CHECK"
        )


    with q2:

        st.metric(
            "V1 Scope Reconciliation",
            "PASS"
            if scope_pass
            else "CHECK"
        )


    with q3:

        st.metric(
            "HHA Outcome Reconciliation",
            "PASS"
            if hha_pass
            else "CHECK"
        )


    with q4:

        st.metric(
            "TAH Reconciliation",
            "PASS"
            if tah_pass
            else "CHECK"
        )


    n1, n2, n3, n4, n5 = st.columns(
        5
    )


    with n1:

        st.metric(
            "V1 Recommendations",
            f"{len(filtered):,}"
        )


    with n2:

        st.metric(
            "HHA Excluded",
            f"{(filtered['Final HHA Result'] == 'Excluded').sum():,}"
        )


    with n3:

        st.metric(
            "HHA Stopped",
            f"{(filtered['Final HHA Result'] == 'Stopped').sum():,}"
        )


    with n4:

        st.metric(
            "HHA Restarted",
            f"{(filtered['Final HHA Result'] == 'Restarted').sum():,}"
        )


    with n5:

        st.metric(
            "Therapy at Home Recommendations",
            f"{len(filtered_tah):,}"
        )


    st.divider()


    # =====================================================
    # EXCLUSION + CONSISTENCY QA
    # =====================================================

    left, right = st.columns(
        2
    )


    with left:

        st.subheader(
            "Hospital / SNF / Hospice Exclusion QA"
        )


        exclusions = filtered[
            filtered[
                "Final HHA Result"
            ]
            == "Excluded"
        ].copy()


        exclusion_columns = [
            "Recommendation ID",
            "MBI Display",
            "ACO Clean",
            "Date Parsed",
            "Recommendation Category",
            "Final HHA Stop Date",
            "Final HHA Result",
            "Final Exclusion Reason"
        ]


        exclusion_columns = [
            column
            for column in exclusion_columns
            if column in exclusions.columns
        ]


        exclusion_display = exclusions[
            exclusion_columns
        ].rename(
            columns={
                "MBI Display": "MBI",
                "ACO Clean": "ACO",
                "Date Parsed": "Recommendation Date",
                "Final HHA Stop Date": "HHA Stop Date"
            }
        )


        st.dataframe(
            exclusion_display,
            use_container_width=True,
            hide_index=True,
            height=300
        )


    with right:

        st.subheader(
            "Claims Consistency QA"
        )


        consistent_qa = filtered[
            filtered[
                "Claims Consistency Status"
            ]
            ==
            "Claims Consistent with Recommendation"
        ].copy()


        consistency_columns = [
            "Recommendation ID",
            "MBI Display",
            "ACO Clean",
            "Date Parsed",
            "Recommendation Category",
            "Final HHA Stop Date",
            "Final HHA Result",
            "Claims Consistency Status"
        ]


        consistency_columns = [
            column
            for column in consistency_columns
            if column in consistent_qa.columns
        ]


        consistency_display = consistent_qa[
            consistency_columns
        ].rename(
            columns={
                "MBI Display": "MBI",
                "ACO Clean": "ACO",
                "Date Parsed": "Recommendation Date",
                "Final HHA Stop Date": "HHA Stop Date"
            }
        )


        st.dataframe(
            consistency_display,
            use_container_width=True,
            hide_index=True,
            height=300
        )


    # =====================================================
    # RESTART + TAH SEQUENCING QA
    # =====================================================

    left, right = st.columns(
        2
    )


    with left:

        st.subheader(
            "Restart QA Cases"
        )


        restart = filtered[
            filtered[
                "Final HHA Result"
            ]
            == "Restarted"
        ].copy()


        restart_columns = [
            "Recommendation ID",
            "MBI Display",
            "ACO Clean",
            "Date Parsed",
            "Recommendation Category",
            "Final HHA Stop Date",
            "Final HHA Result"
        ]


        restart_display = restart[
            restart_columns
        ].rename(
            columns={
                "MBI Display": "MBI",
                "ACO Clean": "ACO",
                "Date Parsed": "Recommendation Date",
                "Final HHA Stop Date": "HHA Stop Date"
            }
        )


        st.dataframe(
            restart_display,
            use_container_width=True,
            hide_index=True,
            height=250
        )


    with right:

        st.subheader(
            "TAH Sequencing QA – Claims Before HHA Stop"
        )


        tah_pre_stop = filtered_tah[
            (
                filtered_tah[
                    "TAH Claim Match Count"
                ]
                > 0
            )
            &
            (
                filtered_tah[
                    "Post-HHA TAH Claim Count"
                ]
                == 0
            )
            &
            (
                filtered_tah[
                    "TAH HHA Stop Date"
                ].notna()
            )
        ].copy()


        tah_qa_columns = [
            "Recommendation ID",
            "MBI Display",
            "ACO Clean",
            "TAH HHA Stop Date",
            "First Any TAH Service Date",
            "TAH Claim Match Count",
            "Post-HHA TAH Claim Count",
            "TAH Result",
            "TAH Evidence Detail"
        ]


        tah_pre_stop_display = tah_pre_stop[
            tah_qa_columns
        ].rename(
            columns={
                "MBI Display": "MBI",
                "ACO Clean": "ACO"
            }
        )


        st.dataframe(
            tah_pre_stop_display,
            use_container_width=True,
            hide_index=True,
            height=250
        )


    # =====================================================
    # TAH SOURCE COVERAGE QA
    # =====================================================

    st.subheader(
        "TAH Source Coverage QA"
    )


    coverage_order = [
        "ASCEND",
        "CCPACO",
        "CHOICE",
        "HORIZON",
        "NJPACO",
        "ORION"
    ]


    coverage_rows = []


    for aco in coverage_order:

        aco_tah = filtered_tah[
            filtered_tah[
                "ACO Clean"
            ]
            == aco
        ]


        count = len(
            aco_tah
        )


        if aco in [
            "CCPACO",
            "NJPACO"
        ]:

            status = (
                "Source Available"
            )

            review_note = (
                "TAH claims source available"
            )


        elif aco == "HORIZON":

            status = (
                "Coverage Confirmation Needed"
            )

            review_note = (
                "Source file exists but current extract "
                "contains zero rows; confirm whether this "
                "represents complete claims coverage."
            )


        else:

            status = (
                "Source Unavailable"
            )

            review_note = (
                "TAH claims source not available "
                "for current validation snapshot"
            )


        coverage_rows.append(
            {
                "ACO":
                    aco,

                "TAH Recommendations":
                    count,

                "Coverage Status":
                    status,

                "QA Note":
                    review_note
            }
        )


    coverage_df = pd.DataFrame(
        coverage_rows
    )


    st.dataframe(
        coverage_df,
        use_container_width=True,
        hide_index=True
    )


    st.info(
        "TAH methodology: Not Found should only be used "
        "when the case is sufficiently mature and therapy "
        "claims coverage is adequate to support that "
        "determination. Unable to Determine remains "
        "appropriate when source coverage is incomplete."
    )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "485 Claims Validation | "
    "Claims snapshot 08/28/2026 | "
    "One row = one recommendation"
)