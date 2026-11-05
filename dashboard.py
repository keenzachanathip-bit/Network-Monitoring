
import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import datetime
from contextlib import closing

DB = Path(__file__).parent / "network_monitor.db"

st.set_page_config(
    page_title="Network Monitor",
    page_icon="📡",
    layout="wide"
)

st.title("📡 Network Monitoring Dashboard")
st.caption("Ubuntu Server | 192.168.56.10")


def load_data():
    with closing(sqlite3.connect(DB, timeout=5)) as conn:
        probes = pd.read_sql_query("""
            SELECT timestamp, reachable,
                   latency_text, packet_loss_pct
            FROM probes
            ORDER BY id DESC LIMIT 120
        """, conn)

        incidents = pd.read_sql_query("""
            SELECT started_at, confirmed_at,
                   recovered_at, failed_probes,
                   downtime_seconds
            FROM incidents
            ORDER BY id DESC LIMIT 20
        """, conn)

        last_seen = conn.execute("""
            SELECT timestamp FROM probes
            WHERE reachable = 1
            ORDER BY id DESC LIMIT 1
        """).fetchone()

    return probes, incidents, last_seen


@st.fragment(run_every="5s")
def live_dashboard():
    if not DB.exists():
        st.warning("Database not found. Run monitor.py first.")
        return

    try:
        probes, incidents, last_seen = load_data()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        return

    if probes.empty:
        st.info("Waiting for monitoring data...")
        return

    latest = probes.iloc[0]
    last_check = datetime.fromisoformat(
        latest["timestamp"]
    )

    age = max(
        0,
        (datetime.now() - last_check).total_seconds()
    )

    # Distinguish monitoring interruption from device failure
    recent = probes.head(3)

    if age > 20:
        status = "MONITORING STALE"
    elif int(latest["reachable"]) == 1:
        status = "REACHABLE"
    elif (
        len(recent) == 3
        and (recent["reachable"] == 0).all()
    ):
        status = "UNREACHABLE"
    else:
        status = "SUSPECT"

    st.subheader("Device Overview")

    a, b, c, d = st.columns(4)

    a.metric("Device Status", status)
    b.metric(
        "Recent Packet Loss",
        f"{latest['packet_loss_pct']:.1f}%"
    )
    c.metric(
        "Last RTT",
        latest["latency_text"] or "N/A"
    )
    d.metric(
        "Last Check",
        f"{age:.0f}s ago"
    )

    if status == "MONITORING STALE":
        st.warning(
            "No recent monitoring samples. "
            "Check whether monitor.py is running."
        )
    elif status == "UNREACHABLE":
        st.error("Device is not responding to ICMP probes.")
    elif status == "SUSPECT":
        st.warning("ICMP probe failures detected.")
    else:
        st.success("Device is responding to ICMP.")

    if last_seen:
        st.caption(f"Last successful reply: {last_seen[0]}")

    st.divider()

    st.subheader("Network Performance")

    chart_data = probes.iloc[::-1].copy()
    chart_data["timestamp"] = pd.to_datetime(
        chart_data["timestamp"]
    )

    st.line_chart(
        chart_data.set_index("timestamp")[
            ["packet_loss_pct"]
        ],
        y_label="Packet Loss (%)"
    )

    st.caption(
        "Packet loss is a rolling metric calculated "
        "by the monitoring backend."
    )

    st.divider()

    st.subheader("Incident History")

    if incidents.empty:
        st.info("No confirmed incidents recorded.")
    else:
        st.dataframe(
            incidents,
            use_container_width=True,
            hide_index=True
        )


live_dashboard()
