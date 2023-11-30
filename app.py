import streamlit as st
import time
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from google.cloud import storage
from google.oauth2 import service_account

# Helper functions to upload and download from GCS
def upload_db_to_gcs(credentials, bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client(credentials=credentials)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    print(f"Uploaded {source_file_name} to {destination_blob_name} in {bucket_name}.")

def download_db_from_gcs(credentials, bucket_name, source_blob_name, destination_file_name):
    """Downloads a blob from the bucket."""
    storage_client = storage.Client(credentials=credentials)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)
    print(f"Downloaded {source_blob_name} from {bucket_name} to {destination_file_name}.")

# Create a credentials object using the service account info from the secrets
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

st.set_page_config(layout="wide")

# Initialize the database and create a table if not present
def init_db():
    with sqlite3.connect("bookings.db") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                room_name TEXT,
                date TEXT,
                start_time TEXT,
                end_time TEXT,
                booking_info TEXT
            )
        """)

# Check if a room is booked for a specific date and timeslot
def is_room_booked(room, date, timeslot):
    with sqlite3.connect("bookings.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM bookings WHERE room_name=? AND date=? AND start_time <= ? AND end_time > ?", (room, date, timeslot, timeslot))
        booking = cur.fetchone()
    return booking

# Check if a room is available for booking for a specific date and timeslot
def is_room_available(room, date, start_time, end_time):
    with sqlite3.connect("bookings.db") as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM bookings WHERE room_name=? AND date=? AND 
            ((start_time > ? AND start_time < ?) OR 
             (end_time > ? AND end_time < ?) OR 
             (start_time <= ? AND end_time > ?) OR
             (start_time >= ? AND end_time <= ?))
        """, (room, date, start_time, end_time, start_time, end_time, start_time, start_time, end_time, start_time))
        booking = cur.fetchone()
    return booking is None

# Delete a specific booking
def delete_booking(room, date, start_time):
    with sqlite3.connect("bookings.db") as conn:
        conn.execute("DELETE FROM bookings WHERE room_name=? AND date=? AND start_time=?", (room, date, start_time))

def get_all_bookings(date):
    with sqlite3.connect("bookings.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM bookings WHERE date=?", (date,))
        bookings = cur.fetchall()
    return bookings


# Check if the database was restored today
def restore_db_if_needed():
    today = datetime.now().date()
    last_restored_date = st.session_state.get("last_restored_date", None)
    
    if last_restored_date != today:
        download_db_from_gcs(credentials, GCS_BUCKET, DB_BKP_NAME, DB_NAME)
        st.session_state.last_restored_date = today  # Update the session state with today's date


GCS_BUCKET = "andreassens.appspot.com"
DB_NAME = "bookings.db"
DB_BKP_NAME = "bookings_prd.db"

init_db()  # Initialize the database
restore_db_if_needed()  # Call the function to potentially restore the database


# Sample rooms
rooms = ['Styrelsen', 'Visionären', 'Innovatören', 'Entreprenören', 'Amatören', 'Coffice']

# Generate time slots
timeslots = [(datetime(2023, 1, 1, 7, 0) + timedelta(minutes=30*i)).strftime('%H:%M') for i in range(25)]

losen = st.text_input('Ange lösenord:', )
if losen == st.secrets["losen"]:

    # Static Sidebar for Booking Form
    with st.sidebar:
        st.write("Booking Form")
        room_selection = st.selectbox("Select Room", rooms)
        timeslot_selection = st.selectbox("Select Timeslot", timeslots)
        end_timeslots = timeslots[timeslots.index(timeslot_selection)+1:]
        end_time_selection = st.selectbox("End Time", end_timeslots)
        booking_info = st.text_area("Your name and Booking Info")
        
        # Checkbox for recurring booking
        recurring_booking = st.checkbox("Recurring Booking")
        
        # Conditionally display the slider based on the checkbox state
        recurring_weeks = 1  # Default value
        if recurring_booking:
            recurring_weeks = st.slider("Number of Weeks (including this week)", 1, 10)

        if st.button("Confirm Booking"):
            if not booking_info:  # Check if booking info is empty
                st.warning("Booking info is mandatory!")
            else:
                # Check availability
                all_dates_available = True
                current_date = st.session_state.selected_date
                for _ in range(recurring_weeks if recurring_booking else 1):
                    if not is_room_available(room_selection, str(current_date), timeslot_selection, end_time_selection):
                        all_dates_available = False
                        break
                    current_date += timedelta(days=7)  # move to next week only if recurring booking

                # Display warning if not all dates are available
                if not all_dates_available:
                    st.sidebar.warning(f"Room is not available for all selected dates. No bookings made!")
                    time.sleep(2)
                    st.experimental_rerun()

                # Booking logic
                try:
                    current_date = st.session_state.selected_date
                    for _ in range(recurring_weeks if recurring_booking else 1):
                        with sqlite3.connect("bookings.db") as conn:
                            conn.execute("INSERT INTO bookings (room_name, date, start_time, end_time, booking_info) VALUES (?, ?, ?, ?, ?)",
                                        (room_selection, str(current_date), timeslot_selection, end_time_selection, booking_info))
                        current_date += timedelta(days=7)
                    
                    if recurring_booking:
                        st.sidebar.success(f"Recurring bookings confirmed for the next {recurring_weeks} weeks!")
                    else:
                        st.sidebar.success("Booking Confirmed!")
                    upload_db_to_gcs(credentials, GCS_BUCKET, DB_NAME, DB_BKP_NAME)
                    st.experimental_rerun()
                except Exception as e:
                    st.sidebar.error(f"Error: {e}")



    # Main Streamlit UI
    st.title("Falkenberg Företagscenter Kvarngatan 2 - Room Booking")

    st.info("""
        Vi har nu ett nytt och förbättrat bokningssystem. Besök länken nedan och skapa ett konto. Om du har bokningar i detta gamla systemet, överför dem så snart som möjligt till det nya systemet.

        Bokningssystemets länk: [https://bookd.xyz](https://bookd.xyz)
    """)

    # Date picker at the top
    if 'selected_date' not in st.session_state:
        st.session_state.selected_date = datetime.now()

    st.session_state.selected_date = st.date_input("Select a date", st.session_state.selected_date)

    # Create a grid layout for rooms vs time slots
    st.write("\n")  # Adds a bit of space

    # Display room names as headers
    header_columns = st.columns(len(rooms) + 1)  # +1 for the timeslot header
    header_columns[0].write("Time Slot")
    for idx, room in enumerate(rooms):
        header_columns[idx + 1].write(room)

    for timeslot in timeslots:
        columns = st.columns(len(rooms) + 1)
        columns[0].write(timeslot)  # Display the timeslot
        for idx, room in enumerate(rooms):
            with columns[idx + 1]:
                booked = is_room_booked(room, str(st.session_state.selected_date), timeslot)
                if booked:
                    if st.button(f"Booked", key=f"Info {room} {timeslot}", help=f"{booked[4]}"):
                        with st.sidebar:
                            st.write(f"Booking Info for {room} at {timeslot} on {st.session_state.selected_date}")
                            st.text(f"Start Time: {booked[2]}")
                            st.text(f"End Time: {booked[3]}")
                            st.text(f"Booking Info: {booked[4]}")


    # Display all bookings in a table with delete option
    st.write("\n\n## All Bookings for the Day")
    bookings_for_the_day = get_all_bookings(str(st.session_state.selected_date))
    if bookings_for_the_day:
        df = pd.DataFrame(bookings_for_the_day, columns=['Room', 'Date', 'Start Time', 'End Time', 'Booking Info'])
        for index, booking in df.iterrows():
            row = st.columns((1, 1, 1, 1, 1, 0.2))
            row[0].write(booking['Room'])
            row[1].write(booking['Date'])
            row[2].write(booking['Start Time'])
            row[3].write(booking['End Time'])
            row[4].write(booking['Booking Info'])
            if row[5].button('🗑️', key=f"delete_{index}"):
                delete_booking(booking['Room'], booking['Date'], booking['Start Time'])
                st.success("Booking Deleted!")
                upload_db_to_gcs(credentials, GCS_BUCKET, DB_NAME, DB_BKP_NAME)
                st.experimental_rerun()
    else:
        st.write("No bookings for the selected date.")

    if st.button("Restore Database"):
        download_db_from_gcs(credentials, GCS_BUCKET, DB_BKP_NAME, DB_NAME)
        st.success("Database downloaded successfully!")
        st.experimental_rerun()
