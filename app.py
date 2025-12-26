import streamlit as st
import sqlite3
import os
from collections import Counter
import csv
import io

# Path to the SQLite database. The database file will be created
# inside the data/ directory if it doesn't exist.
DB_PATH = 'data/database.db'

def init_db() -> None:
    """
    Create the database and tables if they don't exist.
    - events: id, title, event_date, location, topic
    - attendees: id, event_id, name, gender, province
    Renames old 'date' column to 'event_date' if found.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            location TEXT,
            topic TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS attendees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            gender TEXT,
            province TEXT,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
        """
    )
    # If the events table has a 'date' column but not 'event_date', rename it
    info = c.execute("PRAGMA table_info(events)").fetchall()
    column_names = [col[1] for col in info]
    if 'date' in column_names and 'event_date' not in column_names:
        try:
            c.execute('ALTER TABLE events RENAME COLUMN date TO event_date')
            conn.commit()
        except Exception:
            pass
    conn.commit()
    conn.close()

def add_event(title: str, event_date: str, location: str, topic: str = "") -> None:
    """Insert a new event into the database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT INTO events (title, event_date, location, topic) VALUES (?, ?, ?, ?)',
        (title, event_date, location, topic),
    )
    conn.commit()
    conn.close()

def get_events() -> list:
    """Return a list of dicts containing all events."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT id, title, event_date, location, topic FROM events').fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_attendee(event_id: int, name: str, gender: str, province: str = "") -> None:
    """Insert a new attendee tied to a specific event."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT INTO attendees (event_id, name, gender, province) VALUES (?, ?, ?, ?)',
        (event_id, name, gender, province),
    )
    conn.commit()
    conn.close()

def get_attendance_data() -> list:
    """
    Return a list of dicts joining events and attendees for reporting.
    Each dict contains the event title, event date, attendee gender and province.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        '''
        SELECT
            e.title AS event_title,
            e.event_date AS event_date,
            a.gender,
            a.province
        FROM attendees AS a
        JOIN events AS e ON a.event_id = e.id
        '''
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def export_csv(data: list) -> str:
    """Convert a list of dicts to CSV string."""
    if not data:
        return ""
    fieldnames = list(data[0].keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    return buffer.getvalue()

def markdown_table(counts: dict, header1: str, header2: str) -> str:
    """Build a Markdown table from a dictionary of counts."""
    lines = [f"|{header1}|{header2}|", "|---|---|"]
    for key, value in counts.items():
        lines.append(f"|{key}|{value}|")
    return "\n".join(lines)

def main():
    """Main entry point for the Streamlit application."""
    st.set_page_config(page_title="AgriImpact Insight", layout="wide")
    st.title("AgriImpact Insight (No Pandas)")
    init_db()

    tab1, tab2, tab3 = st.tabs([
        "Add Event",
        "Register Attendee",
        "View Reports",
    ])

    # ---- Tab 1: Add Event ----
    with tab1:
        st.header("Add New Event")
        with st.form("event_form"):
            title = st.text_input("Event Title")
            date_value = st.date_input("Event Date")
            location = st.text_input("Location")
            topic = st.text_input("Topic (optional)")
            submitted = st.form_submit_button("Add Event")
            if submitted:
                if title:
                    add_event(title, date_value.isoformat(), location, topic)
                    st.success("Event added successfully.")
                else:
                    st.error("Please provide an event title.")

    # ---- Tab 2: Register Attendee ----
    with tab2:
        st.header("Register Attendee")
        events = get_events()
        if not events:
            st.info("Please add an event first.")
        else:
            event_options = {
                f"{e['title']} ({e['event_date']})": e['id'] for e in events
            }
            with st.form("attendee_form"):
                selected_event = st.selectbox("Select Event", list(event_options.keys()))
                attendee_name = st.text_input("Attendee Name")
                gender = st.selectbox("Gender", ["Male", "Female", "Other", "Prefer not to say"])
                province = st.text_input("Province")
                submit_attendee = st.form_submit_button("Register Attendee")
                if submit_attendee:
                    if attendee_name:
                        add_attendee(
                            event_options[selected_event],
                            attendee_name,
                            gender,
                            province,
                        )
                        st.success("Attendee registered successfully.")
                    else:
                        st.error("Please provide the attendee's name.")

    # ---- Tab 3: View Reports ----
    with tab3:
        st.header("Attendance & Impact Reports")
        data = get_attendance_data()
        if not data:
            st.info("No attendance data available.")
        else:
            # Summary metrics
            total_events = len(get_events())
            total_attendees = len(data)
            st.metric("Total Events", total_events)
            st.metric("Total Attendees", total_attendees)

            # Aggregate counts
            events_counts = Counter(item['event_title'] for item in data)
            gender_counts = Counter(item['gender'] for item in data)
            province_counts = Counter(item['province'] for item in data)

            st.subheader("Attendance by Event")
            st.markdown(markdown_table(events_counts, "Event", "Count"))

            st.subheader("Attendance by Gender")
            st.markdown(markdown_table(gender_counts, "Gender", "Count"))

            st.subheader("Attendance by Province")
            st.markdown(markdown_table(province_counts, "Province", "Count"))

            # CSV export
            csv_data = export_csv(data)
            st.download_button(
                label="Download Attendance CSV",
                data=csv_data,
                file_name='attendance_data.csv',
                mime='text/csv',
            )

if __name__ == "__main__":
    main()
