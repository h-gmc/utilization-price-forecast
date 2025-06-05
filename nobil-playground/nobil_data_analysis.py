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
METADATA_PATH = os.path.join("data2", "NOBILdump_SWE_forever-2025-06-03.json")
# Duckdb connection
con = duckdb.connect("database.db")

# ------------------------
# Data Loading & Parsing
# ------------------------

def load_charger_statuses(tar_path, read_first=None):
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
            # For reading only a part of the data
            if read_first is not None and i > read_first:
                break

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
    text_value_con_attrs = [1, 4, 5, 17, 19, 20, 25, 26]

    for station in meta.get("chargerstations", []):
        csmd = station.get("csmd", {})
        attrs = station.get("attr", {})
        st = attrs.get("st", {})
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

        site_dict = {
            "site_id": site_id,
            "site_name": csmd.get("name"),
            "operator": csmd.get("Operator"),
            "owner": csmd.get("Owned_by"),
            "street": csmd.get("Street"),
            "zipcode": csmd.get("Zipcode"),
            "city": csmd.get("City"),
            "municipality": csmd.get("Municipality"),
            "county": csmd.get("County"),
            "latitude": lat,
            "longitude": lon,
        }
        for _, v in st.items():
            site_dict[v['attrname']] = v['trans']
        sites.append(site_dict)

        # ------------------------
        # Charger-level metadata
        # ------------------------
        for _, conn_attrs in conn_map.items():
            charger_id = conn_attrs.get("28", {}).get("attrval")  # EVSE ID
            if not charger_id:
                continue
            charger_dict = {
                "charger_id": charger_id,
                "site_id": site_id,
            }
            for k, v in conn_attrs.items():
                value = v['trans'] if int(k) in text_value_con_attrs else v['attrval']
                charger_dict[v['attrname']] = value
            chargers.append(charger_dict)

    return pd.DataFrame(sites), pd.DataFrame(chargers)

# ------------------------
# Main Execution
# ------------------------

if __name__ == "__main__":
    sessions_in_duckdb = True
    if not sessions_in_duckdb:

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
        # Build DataFrame from sessions
        # ----------------------------
        sessions_df = pd.DataFrame(sessions, columns=["site_id", "charger_id", "start", "end", "duration"])
        sessions_df["start_dt"] = pd.to_datetime(sessions_df["start"], unit="s")
        sessions_df["hour"] = sessions_df["start_dt"].dt.floor("h")
        sessions_df["day"] = sessions_df["start_dt"].dt.date
        con.execute("DROP TABLE IF EXISTS session")
        con.execute("CREATE TABLE session AS SELECT * FROM sessions_df")

    metadata_in_duckdb = True
    if not metadata_in_duckdb:
        # ----------------------------
        # Load and inspect metadata
        # ----------------------------
        site_metadata_df, charger_metadata_df = load_metadata(METADATA_PATH)
        con.execute("DROP TABLE IF EXISTS charger")
        con.execute("CREATE TABLE charger AS SELECT * FROM charger_metadata_df")
        con.execute("DROP TABLE IF EXISTS site")
        con.execute("CREATE TABLE site AS SELECT * FROM site_metadata_df")


    # ----------------------------
    # DuckDB UI
    # ----------------------------
    con.execute("CALL start_ui_server()")
    print("Duckdb UI started on http://localhost:4213")
    input("Press enter to stop")
