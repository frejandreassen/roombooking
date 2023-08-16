import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import pandas as pd

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
            ((start_time BETWEEN ? AND ?) OR (end_time BETWEEN ? AND ?) OR (start_time <= ? AND end_time >= ?))
        """, (room, date, start_time, end_time, start_time, end_time, start_time, end_time))
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

init_db()  # Initialize the database

# Sample rooms
rooms = ['Styrelsen', 'Visionären', 'Innovatören', 'Entreprenören', 'Amatören', 'Coffice']

# Generate time slots
timeslots = [(datetime(2023, 1, 1, 7, 0) + timedelta(minutes=30*i)).strftime('%H:%M') for i in range(25)]


if st.text_input('Ange lösenord:', ) == st.secrets["losen"]:

    # Static Sidebar for Booking Form
    with st.sidebar:
        st.write("Booking Form")
        room_selection = st.selectbox("Select Room", rooms)
        timeslot_selection = st.selectbox("Select Timeslot", timeslots)
        
        # Create a dynamic end timeslot selection that starts from the selected timeslot
        end_timeslots = timeslots[timeslots.index(timeslot_selection)+1:]
        end_time_selection = st.selectbox("End Time", end_timeslots)
        
        booking_info = st.text_area("Booking Info")

        if st.button("Confirm Booking"):
            if is_room_available(room_selection, str(st.session_state.selected_date), timeslot_selection, end_time_selection):
                try:
                    with sqlite3.connect("bookings.db") as conn:
                        conn.execute("INSERT INTO bookings (room_name, date, start_time, end_time, booking_info) VALUES (?, ?, ?, ?, ?)", 
                                    (room_selection, str(st.session_state.selected_date), timeslot_selection, end_time_selection, booking_info))
                    st.sidebar.success("Booking Confirmed!")
                except Exception as e:
                    st.sidebar.error(f"Error: {e}")
            else:
                st.sidebar.warning("Room is already booked for the selected timeslot!")


    # Main Streamlit UI
    st.title("Falkenberg Företagscenter Kvarngatan 2 - Room Booking")

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
                st.experimental_rerun()
    else:
        st.write("No bookings for the selected date.")