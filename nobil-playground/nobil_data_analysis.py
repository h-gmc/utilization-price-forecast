import tarfile
import pandas as pd
import duckdb
import json
import os
from collections import defaultdict

# ------------------------
# Configuration
# ------------------------

TAR_PATH = os.path.join("data2", "2025-05-26.tar.gz")
METADATA_PATH = os.path.join("data2", "metadata.json")

# ------------------------
# Data Loading & Parsing
# ------------------------

def load_charger_statuses(tar_path):
    """
    Streams and parses a .tar.gz file containing JSON timeseries data,
    grouping by (nobilId, evseUid) and sorting each group's entries by timestamp.

    Returns:
        dict: {
            (nobilId, evseUid): [(timestamp, status), ...],
            ...
        }
    """
    charger_logs = defaultdict(list)

    print(f"[INFO] Opening tar file: {tar_path}")
    with tarfile.open(tar_path, mode="r:gz") as tar:
        print(f"[INFO] Streaming archive contents...")
        for i, member in enumerate(tar):
            if not member.isfile() or not member.name.startswith("data/"):
                continue

            f = tar.extractfile(member)
            if f is not None:
                try:
                    content = f.read().decode("utf-8")
                    entry = json.loads(content)

                    site_id = entry.get("nobilId")
                    charger_id = entry.get("evseUid")
                    status = entry.get("status")
                    timestamp = entry.get("timestamp")

                    if all([site_id, charger_id, status, timestamp]):
                        key = (site_id, charger_id)
                        charger_logs[key].append((timestamp, status))
                except Exception as e:
                    print(f"[ERROR] Failed to parse {member.name}: {e}")

            if i % 1000 == 0:
                print(f"[PROGRESS] Processed {i} files...")

    print(f"[INFO] Sorting timestamps for each charger...")
    for key in charger_logs:
        charger_logs[key].sort()

    print(f"[DONE] Parsed {len(charger_logs)} unique chargers.")
    return charger_logs

# ------------------------
# Status Inspection
# ------------------------

def get_all_unique_statuses(charger_logs):
    """
    Scans all logs and returns a sorted set of all unique status values found.
    """
    statuses = set()
    for entries in charger_logs.values():
        for _, status in entries:
            statuses.add(status)
    return sorted(statuses)

# ------------------------
# Charging Session Logic
# ------------------------

def extract_charging_sessions(charger_logs):
    """
    Extracts charging sessions based on status transitions.

    A session starts on CHARGING and ends on one of:
    AVAILABLE, BLOCKED, OUTOFORDER, UNKNOWN

    Ignores RESERVED transitions.
    """
    sessions = []

    session_end_statuses = {"AVAILABLE", "BLOCKED", "OUTOFORDER", "UNKNOWN"}

    for (site_id, charger_id), events in charger_logs.items():
        charging_start = None

        for ts, status in events:
            if status == "CHARGING" and charging_start is None:
                charging_start = ts
            elif status in session_end_statuses and charging_start is not None:
                duration = ts - charging_start
                sessions.append((site_id, charger_id, charging_start, ts, duration))
                charging_start = None

    return sessions

def load_metadata(metadata_path):
    """
    Parses metadata into two DataFrames:
    - site_metadata_df: site-level info (e.g., operator, address, location)
    - charger_metadata_df: charger-level info (e.g., EVSE ID, power, connector type)
    """

    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    sites = []
    chargers = []

    for station in meta.get("chargerstations", []):
        csmd = station.get("csmd", {})
        attrs = station.get("attr", {})
        conn_map = attrs.get("conn", {})

        # ------------------------
        # Site-level metadata
        # ------------------------
        site_id = csmd.get("International_id")

        # Parse (lat, lon) tuple
        pos = csmd.get("Position")
        lat, lon = None, None

        if isinstance(pos, dict):
            lat = pos.get("Latitude")
            lon = pos.get("Longitude")
        elif isinstance(pos, str) and pos.startswith("("):
            try:
                lat_str, lon_str = pos.strip("()").split(",")
                lat, lon = float(lat_str), float(lon_str)
            except ValueError:
                pass  # Leave lat/lon as None


        sites.append({
            "site_id": site_id,
            "site_name": csmd.get("Name"),
            "operator": csmd.get("Operator"),
            "owner": csmd.get("Owned_by"),
            "street": csmd.get("Street"),
            "zipcode": csmd.get("Zipcode"),
            "city": csmd.get("City"),
            "municipality": csmd.get("Municipality"),
            "county": csmd.get("County"),
            "latitude": lat,
            "longitude": lon,
            "availability": csmd.get("attrname: Availability"),
            "open_24h": csmd.get("attrname: Open 24h"),
            "accessibility": csmd.get("attrname: Accessibility"),
        })

        # ------------------------
        # Charger-level metadata
        # ------------------------
        for conn_key, conn_attrs in conn_map.items():
            charger_id = conn_attrs.get("28", {}).get("attrval")  # EVSE ID
            if not charger_id:
                continue

            chargers.append({
                "charger_id": charger_id,
                "site_id": site_id,
                "power_kW": conn_attrs.get("24", {}).get("attrval"),
                "connector_type": conn_attrs.get("20", {}).get("attrval"),
                "amperage": conn_attrs.get("attrname: Amperage (A)", {}).get("attrval"),
                "charge_mode": conn_attrs.get("attrname: Charge mode", {}).get("attrval"),
                "voltage": conn_attrs.get("attrname: Voltage (V)", {}).get("attrval"),
                "fixed_cable": conn_attrs.get("attrname: Fixed cable", {}).get("attrval"),
                "payment_methods": conn_attrs.get("attrname: Payment method", {}).get("attrval"),
            })

    site_metadata_df = pd.DataFrame(sites)
    charger_metadata_df = pd.DataFrame(chargers)

    return site_metadata_df, charger_metadata_df

# ------------------------
# Main Execution
# ------------------------

if __name__ == "__main__":
    # ----------------------------
    # Load and parse session data
    # ----------------------------
    charger_logs = load_charger_statuses(TAR_PATH)

    # Inspect all unique statuses
    unique_statuses = get_all_unique_statuses(charger_logs)
    print("\n[INFO] Unique status values in data:")
    for s in unique_statuses:
        print(f" - {s}")

    # Extract sessions from logs
    sessions = extract_charging_sessions(charger_logs)

    # ----------------------------
    # Load and inspect metadata
    # ----------------------------
    site_metadata_df, charger_metadata_df = load_metadata(METADATA_PATH)

    print("\n[INFO] Site metadata sample:")
    print(site_metadata_df.head(2))
    print("\n[INFO] Charger metadata sample:")
    print(charger_metadata_df.head(2))

    # ----------------------------
    # Build DataFrame from sessions
    # ----------------------------
    df = pd.DataFrame(sessions, columns=["site_id", "charger_id", "start", "end", "duration"])
    df["start_dt"] = pd.to_datetime(df["start"], unit="s")
    df["hour"] = df["start_dt"].dt.floor("H")
    df["day"] = df["start_dt"].dt.date

    # ----------------------------
    # Sample output
    # ----------------------------
    print("\n[INFO] Sample charging sessions:")
    for session in sessions[:10]:
        site, charger, start, end, dur = session
        print(f"{site} | {charger} | Start: {start} | End: {end} | Duration: {dur}s")

    # ----------------------------
    # DuckDB query
    # ----------------------------
    print("\n[INFO] Running first DuckDB query: total charge time per site per hour...")
    result = duckdb.query("""
        SELECT site_id, hour, SUM(duration) AS total_seconds
        FROM df
        GROUP BY site_id, hour
        ORDER BY hour
    """).to_df()

    print(result.head(10))
