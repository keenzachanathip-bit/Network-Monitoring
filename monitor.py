
import subprocess
import sqlite3
import re
import time
from collections import deque
from datetime import datetime

TARGET = "192.168.56.10"
INTERVAL = 5
TIMEOUT_MS = 1000
FAIL_THRESHOLD = 3
WINDOW = 60
DB_FILE = "network_monitor.db"

db = sqlite3.connect(DB_FILE)

db.execute("""
CREATE TABLE IF NOT EXISTS probes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    target_ip TEXT,
    reachable INTEGER,
    latency_ms REAL,
    latency_text TEXT,
    packet_loss_pct REAL
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    target_ip TEXT,
    event_type TEXT
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_ip TEXT,
    started_at TEXT,
    confirmed_at TEXT,
    recovered_at TEXT,
    failed_probes INTEGER,
    downtime_seconds REAL
)
""")
db.commit()


def ping_server():
    try:
        result = subprocess.run(
            ["ping", "-4", "-n", "1",
             "-w", str(TIMEOUT_MS), TARGET],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=3
        )
    except subprocess.TimeoutExpired:
        return False, None, "N/A"

    output = result.stdout + result.stderr

    # Check for an ICMP Echo Reply
    success = (
        result.returncode == 0
        and re.search(r"\bTTL\s*=\s*\d+", output, re.I)
        is not None
    )

    if not success:
        return False, None, "N/A"

    match = re.search(
        r"\btime\s*(=|<)\s*(\d+(?:\.\d+)?)\s*ms",
        output, re.I
    )

    if not match:
        return True, None, "N/A"

    value = float(match.group(2))

    if match.group(1) == "<":
        return True, None, f"<{value:g} ms"

    return True, value, f"{value:g} ms"


def event(timestamp, name):
    db.execute(
        """INSERT INTO events
           (timestamp, target_ip, event_type)
           VALUES (?, ?, ?)""",
        (timestamp, TARGET, name)
    )


def format_duration(seconds):
    seconds = int(seconds)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


history = deque(maxlen=WINDOW)
state = "UNKNOWN"
failures = 0
checks = 0
first_failure_mono = None
first_failure_at = None
incident_id = None

row = db.execute(
    """SELECT timestamp FROM probes
       WHERE target_ip = ? AND reachable = 1
       ORDER BY id DESC LIMIT 1""",
    (TARGET,)
).fetchone()

last_seen = row[0] if row else "Never"

print("=" * 50)
print("KEEN's NETWORK MONITORING SYSTEM")
print(f"Target       : {TARGET}")
print(f"Check every  : {INTERVAL} seconds")
print(f"Down after   : {FAIL_THRESHOLD} failed probes")
print("Ctrl+C to stop")
print("=" * 50)

try:
    while True:
        cycle_start = time.monotonic()
        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        checks += 1
        success, latency, latency_text = ping_server()

        history.append(1 if success else 0)

        packet_loss = (
            (len(history) - sum(history))
            / len(history) * 100
        )

        if success:
            if state == "DOWN":
                duration = (
                    time.monotonic()
                    - first_failure_mono
                )

                db.execute(
                    """UPDATE incidents SET
                       recovered_at = ?,
                       failed_probes = ?,
                       downtime_seconds = ?
                       WHERE id = ?""",
                    (
                        timestamp,
                        failures,
                        round(duration, 2),
                        incident_id
                    )
                )

                event(timestamp, "RECOVERY")
                print(
                    f"[{timestamp}] RECOVERED | "
                    f"Outage: {format_duration(duration)} | "
                    f"Missed: {failures} probes"
                )

            elif failures > 0:
                print(
                    f"[{timestamp}] RESTORED | "
                    f"Transient failures: {failures} | "
                    f"No DOWN incident"
                )

            elif state == "UNKNOWN":
                event(timestamp, "ONLINE")
                print(
                    f"[{timestamp}] ONLINE | "
                    f"RTT: {latency_text}"
                )

            elif checks % 6 == 0:
                print(
                    f"[{timestamp}] REACHABLE | "
                    f"RTT: {latency_text} | "
		    f"Loss(last {len(history)}): "
                    f"{packet_loss:.1f}%"
                )

            state = "UP"
            failures = 0
            last_seen = timestamp
            first_failure_mono = None
            incident_id = None

        else:
            failures += 1

            if failures == 1:
                first_failure_mono = cycle_start
                first_failure_at = timestamp

            duration = (
                time.monotonic()
                - first_failure_mono
            )

            if failures < FAIL_THRESHOLD:
                print(
                    f"[{timestamp}] SUSPECT | "
                    f"Missed {failures}/{FAIL_THRESHOLD} | "
                    f"Last seen: {last_seen}"
                )

            elif failures == FAIL_THRESHOLD:
                state = "DOWN"

                cursor = db.execute(
                    """INSERT INTO incidents
                       (target_ip, started_at,
                        confirmed_at, failed_probes)
                       VALUES (?, ?, ?, ?)""",
                    (
                        TARGET, first_failure_at,
                        timestamp, failures
                    )
                )
                incident_id = cursor.lastrowid

                event(timestamp, "DOWN")

                print(
                    f"[{timestamp}] ALERT: UNREACHABLE | "
                    f"{failures} consecutive failures | "
                    f"Last seen: {last_seen}"
                )

            else:
                print(
                    f"[{timestamp}] STILL UNREACHABLE | "
                    f"Missed: {failures} | "
                    f"Elapsed: {format_duration(duration)}"
                )

        db.execute(
            """INSERT INTO probes
               (timestamp, target_ip, reachable,
                latency_ms, latency_text, packet_loss_pct)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                timestamp, TARGET, int(success),
                latency, latency_text,
                round(packet_loss, 2)
            )
        )

        db.commit()

        elapsed = time.monotonic() - cycle_start
        time.sleep(max(0, INTERVAL - elapsed))

except KeyboardInterrupt:
    print("\nMonitoring stopped.")

finally:
    db.close()
