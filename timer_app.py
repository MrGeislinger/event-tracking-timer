import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
import uuid
import os

# --- Configuration & Setup ---
LOG_FILE = "log.csv"
LOG_COLUMNS = [
    "session_id", "timestamp", "event", "title", "tags",
    "description", "duration_minutes", "elapsed_seconds"
]

# --- Helper Functions ---

def initialize_log_file():
    """Create the log file with headers if it doesn't exist."""
    if not os.path.exists(LOG_FILE):
        df = pd.DataFrame(columns=LOG_COLUMNS)
        df.to_csv(LOG_FILE, index=False)

def log_event(session_id, event, title="", tags=None, description="", duration_minutes=0, elapsed_seconds=0):
    """Appends an event to the CSV log file."""
    if tags is None:
        tags = []
    
    new_entry = pd.DataFrame([{
        "session_id": session_id,
        "timestamp": datetime.now(),
        "event": event,
        "title": title,
        "tags": ", ".join(tags),
        "description": description,
        "duration_minutes": duration_minutes,
        "elapsed_seconds": elapsed_seconds
    }])
    log_df = pd.read_csv(LOG_FILE)
    log_df = pd.concat([log_df, new_entry], ignore_index=True)
    log_df.to_csv(LOG_FILE, index=False)


def get_log_data():
    """Reads and returns the log file as a DataFrame."""
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame(columns=LOG_COLUMNS)
    return pd.read_csv(LOG_FILE)


def get_all_tags(df):
    """Extracts a sorted list of unique tags from the log data."""
    if df.empty or 'tags' not in df.columns or df['tags'].isnull().all():
        return []
    tags = set()
    df['tags'].dropna().str.split(', ').apply(tags.update)
    return sorted(list(filter(None, tags)))


def get_past_sessions(df):
    """Processes the log DataFrame to show a summary of past sessions."""
    if df.empty:
        return pd.DataFrame()

    sessions = []
    for session_id, group in df.groupby('session_id'):
        start_event = group[group['event'] == 'start']
        end_event = group[group['event'].isin(['finish', 'stop'])]
        
        if not start_event.empty:
            session_info = {
                'Title': start_event.iloc[0]['title'],
                'Tags': start_event.iloc[0]['tags'],
                'Set Duration (min)': start_event.iloc[0]['duration_minutes']
            }
            if not end_event.empty:
                elapsed = end_event.iloc[0]['elapsed_seconds']
                session_info['Actual Elapsed Time'] = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
                session_info['Status'] = 'Completed' if end_event.iloc[0]['event'] == 'finish' else 'Stopped'
            else:
                session_info['Actual Elapsed Time'] = 'In Progress'
                session_info['Status'] = 'Running'
            sessions.append(session_info)
            
    return pd.DataFrame(sessions).sort_index(ascending=False)

# --- App State Initialization ---

initialize_log_file()

if 'app_state' not in st.session_state:
    st.session_state.app_state = 'main'
    st.session_state.timer_end_time = None
    st.session_state.timer_start_time = None
    st.session_state.session_id = None
    st.session_state.session_info = {}


# --- UI Rendering ---

st.set_page_config(page_title="Streamlit Timer", layout="centered")

# === MAIN VIEW: SETUP NEW TIMER ===
if st.session_state.app_state == 'main':
    st.title("⏱️ Countdown Timer")
    st.markdown("---")

    log_df = get_log_data()
    all_tags = get_all_tags(log_df)

    with st.form("timer_form"):
        st.subheader("Create a New Timer")
        duration = st.number_input("Countdown Time (minutes)", min_value=1, value=20, step=1)
        title = st.text_input("Title", placeholder="e.g., Work on project report")
        
        # MODIFIED: Changed the multiselect to only handle existing tags
        selected_tags = st.multiselect("Select existing tags", options=all_tags, default=[])

        # NEW: Text input for adding new tags
        new_tags_str = st.text_input("Add new tags (comma-separated)", placeholder="e.g., project-alpha, urgent")
        
        description = st.text_area("Description (optional)")
        submitted = st.form_submit_button("🚀 Start Countdown")

        if submitted:
            if not title:
                st.error("Please provide a title for the timer.")
            else:
                # MODIFIED: Combine tags from both inputs
                new_tags = [tag.strip() for tag in new_tags_str.split(',') if tag.strip()]
                final_tags = sorted(list(set(selected_tags + new_tags)))
                
                # Set session state for the new timer
                st.session_state.app_state = 'timing'
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.timer_start_time = datetime.now()
                st.session_state.timer_end_time = st.session_state.timer_start_time + timedelta(minutes=duration)
                st.session_state.session_info = {
                    "title": title, "tags": final_tags, "description": description, "duration": duration
                }
                
                # Log the start event
                log_event(
                    session_id=st.session_state.session_id,
                    event='start',
                    title=title,
                    tags=final_tags,
                    description=description,
                    duration_minutes=duration
                )
                st.rerun()

    st.markdown("---")
    st.subheader("📊 Past Sessions")
    past_sessions_df = get_past_sessions(log_df)
    if not past_sessions_df.empty:
        st.dataframe(past_sessions_df, use_container_width=True)
    else:
        st.info("No past timer sessions found. Start one above!")

# === TIMER VIEW: COUNTDOWN IN PROGRESS ===
elif st.session_state.app_state == 'timing':
    info = st.session_state.session_info
    st.title(f"⏳ Counting down: {info['title']}")
    st.write(f"**Tags:** `{', '.join(info['tags'])}`" if info['tags'] else "")
    
    timer_placeholder = st.empty()
    
    if st.button("🛑 Stop Timer", use_container_width=True):
        elapsed = (datetime.now() - st.session_state.timer_start_time).total_seconds()
        log_event(st.session_state.session_id, 'stop', elapsed_seconds=elapsed)
        st.session_state.app_state = 'main'
        st.rerun()

    while datetime.now() < st.session_state.timer_end_time:
        remaining = st.session_state.timer_end_time - datetime.now()
        minutes, seconds = divmod(int(remaining.total_seconds()), 60)
        timer_placeholder.metric("Time Remaining", f"{minutes:02d}:{seconds:02d}")
        time.sleep(1)
    
    # This part runs once the loop above finishes
    timer_placeholder.metric("Time Remaining", "00:00")
    st.session_state.app_state = 'alarm'
    elapsed = (datetime.now() - st.session_state.timer_start_time).total_seconds()
    log_event(st.session_state.session_id, 'finish', elapsed_seconds=elapsed)
    st.rerun()

# === ALARM VIEW: TIMER FINISHED ===
elif st.session_state.app_state == 'alarm':
    st.title("🎉 Time's Up!")
    st.success(f"You completed your session: **{st.session_state.session_info['title']}**")
    
    # Autoplay a short sound
    st.audio('alarm_sound.wav', autoplay=True)
    
    if st.button("✅ Acknowledge and Return", use_container_width=True):
        log_event(st.session_state.session_id, 'acknowledge')
        st.session_state.app_state = 'main'
        st.rerun()