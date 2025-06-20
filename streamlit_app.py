import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
import pandas as pd
import numpy as np
import altair as alt
import time
import os
import json

# enable usability test
st.set_page_config(page_title="Alternative Fuel Finder- Usability Test", layout="wide")

#JSON credentials
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# JSON credentials from Streamlit secrets
creds_info = st.secrets["GOOGLE_CREDS"]
creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
client = gspread.authorize(creds)

spreadsheet_id = '1nTTbqs2ZPr_mcT24QgMAmem8S7p6jhFcQWvUAC6LCLI'
sheet = client.open_by_key(spreadsheet_id).sheet1

data = sheet.get_all_records()
df = pd.DataFrame(data)



# Initialize session state for task timing
if "task_start_times" not in st.session_state:
    st.session_state.task_start_times = {}

if "task_success" not in st.session_state:
    st.session_state.task_success = {
        "Task 1": False,
        "Task 2": False,
        "Task 3": False,
    }

if "task_durations" not in st.session_state:
    st.session_state.task_durations = {
        "Task 1": 0,
        "Task 2": 0,
        "Task 3": 0,
    }



#utility functions
def mark_task_start(task_name):
    st.session_state.task_start_times[task_name] = time.time()

def mark_task_end(task_name):
    start = st.session_state.task_start_times.get(task_name)
    if start:
        duration = time.time() - start
        st.session_state.task_durations[task_name] = duration
    else:
        st.session_state.task_durations[task_name] = None

def go_next():
    if st.session_state.current_step == "intro":
        st.session_state.current_step = "Task 1"
    elif st.session_state.current_step == "Task 1":
        st.session_state.current_step = "Task 2"
    elif st.session_state.current_step == "Task 2":
        st.session_state.current_step = "Task 3"
    elif st.session_state.current_step == "Task 3":
        st.session_state.current_step = "Feedback"


def go_back(to="search"):
    st.session_state.current_step = to


# session state setup
if "current_step" not in st.session_state:
    st.session_state.current_step = "intro"
if "stations" not in st.session_state:
    st.session_state.stations = None
    st.session_state.locations = None

# intro to usability test
if st.session_state.current_step == "intro":
    st.title("Usability Test: Alternative Fuel Finder")

    st.markdown("""
    Welcome! You will be participating in a usability test for a tool that helps users 
    find alternative fuel locations in their desired area. 

    ** Instructions **
    - Complete each task in the order presented
    - Provide honest feedback based on your experience, and submit!
    - There is no technical experience needed to complete this test.
    """)
    if st.button("Start Task 1"):
        go_next()
        st.rerun()

# User input location
elif st.session_state.current_step == "Task 1":
    if "Task 1" not in st.session_state.task_start_times:
        mark_task_start("Task 1")
    st.header("Task 1: Search for Alternative Fuel Stations")
    location = st.text_input("Enter city, address or zip code")
    # find by fuel type
    fuel_type_options = ["ELEC", "LPG", "CNG", "E85", "HY", "LNG", "BD", "RD"]
    selected_fuel_types = st.multiselect("Select one or more fuel type:",
                                         options=fuel_type_options,
                                         default=["ELEC"]
                                         )
    max_results = st.slider("Number of stations to retrieve", 10, 100, step=10)

    # initialize session state for stations data
    if "stations" not in st.session_state:
        st.session_state.stations = None
        st.session_state.locations = None

    # button to call API
    if st.button("Search for Fuel: Continue to Task 2"):
        if not location.strip():
            st.error("Please enter a city, address or zip code")
        elif not selected_fuel_types:
            st.error("Please select one or more fuel type")
        else:

            # extract user geo location lat/ long
            geo_url = "https://nominatim.openstreetmap.org/search"
            geo_params = {
                "q": location,
                "format": "json",
                "limit": 1
            }
            geo_response = requests.get(geo_url, params=geo_params, headers={"User-Agent": "Alternative Fuel Finder"})

            if geo_response.status_code == 200 and geo_response.json():
                geo_data = geo_response.json()[0]
                lat = float(geo_data["lat"])
                lon = float(geo_data["lon"])
                # st.write(f"Found Coordinates: Latitude: {lat}, Longitude: {lon}")

                # call NREL API with lat/lon
                api_key = "rsTWzqEBL7QktFeJtajUH91vbJBYkHhwTjAV1eLl"
                nrel_url = "https://developer.nrel.gov/api/alt-fuel-stations/v1/nearest.json"
                nrel_params = {
                    "api_key": api_key,
                    "latitude": lat,
                    "longitude": lon,
                    "limit": max_results,
                    "fuel_type": ",".join(selected_fuel_types)
                }

                nrel_response = requests.get(nrel_url, params=nrel_params)

                if nrel_response.status_code == 200:
                    stations = nrel_response.json().get("fuel_stations", [])
                    if stations:
                        st.session_state.stations = stations

                        # prep locations for map
                        locations = []

                        for station in stations:
                            lat = station.get("latitude")
                            lon = station.get("longitude")
                            if lat and lon:
                                locations.append({"lat": float(lat), "lon": float(lon)})
                        st.session_state.locations = locations
                        st.session_state.search_location = location.strip()

                        #mark task completion
                        mark_task_end("Task 1")
                        st.session_state.task_success["Task 1"] = True
                        st.session_state.current_step = "Task 2"
                        st.rerun()
                    else:
                        st.warning("No fuel stations found near this location.")

                else:
                    st.error("Error retrieving fuel station data.")
            else:
                st.error("Location could not be found.")


# Search Results
elif st.session_state.current_step == "Task 2":
    if "Task 2" not in st.session_state.task_start_times:
        mark_task_start("Task 2")
    st.header("Task 2: View & Filter Results")

    if st.session_state.stations:
        st.subheader("Fuel Stations Found")

        # checkbox for map
        show_map = st.checkbox("Show Map View")
        if show_map:
            if st.session_state.locations:
                df_locations = pd.DataFrame(st.session_state.locations)
                st.map(df_locations)
            else:
                st.warning("No fuel stations available to display on map. ")
        else:
            # show table
            keys = ["station_name", "street_address", "city", "state", "zip", ]
            stations_fixed = []
            for s in st.session_state.stations:
                fixed = {
                    "station_name": s.get("station_name", ""),
                    "street_address": s.get("street_address", ""),
                    "city": s.get("city", ""),
                    "state": s.get("state", ""),
                    "zip": s.get("zip", ""),
                }
                stations_fixed.append(fixed)
            df_table = pd.DataFrame(stations_fixed)
            df_table.columns = keys

            st.subheader(f"Table of Locations")
            st.dataframe(df_table)
            st.write("---")

        st.subheader(f"Nearest Fuel Stations")
        for station in st.session_state.stations:
            st.markdown(f"**{station['station_name']}**")
            st.write(
                f"{station.get('street_address')}, {station.get('city')}, {station.get('state')}, {station.get('zip', 'N/A')}")
            st.write(f"Fuel Type: {station['fuel_type_code']}")
            st.write("---")

        st.success(
            f"Found {len(st.session_state.stations)} fuel stations near your {st.session_state.search_location}.")

        # bar chart for fuel type counts
        from collections import Counter

        fuel_type_names = {
            "ELEC": "Electric",
            "LPG": "Liquified Petroleum Gas",
            "CNG": "Compressed Natural Gas",
            "E85": "Ethanol (E85)",
            "HY": "Hydrogen",
            "LNG": "Liquified Natural Gas",
            "BD": "Biodiesel",
            "RD": "Renewable Diesel",
        }

        fuel_counts = {name: 0 for name in fuel_type_names.values()}
        for station in st.session_state.stations:
            ft_code = station.get("fuel_type_code")
            ft_name = fuel_type_names.get(ft_code, ft_code)
            fuel_counts[ft_name] = fuel_counts.get(ft_name, 0) + 1
        fuel_codes = [s.get("fuel_type_code") for s in st.session_state.stations]
        counts = Counter(fuel_codes)

        df_fuel_counts = pd.DataFrame({
            "Fuel Type": list(fuel_counts.keys()),
            "Fuel Count": list(fuel_counts.values())
        }).sort_values(by="Fuel Count", ascending=False)

        st.subheader(f"Fuel Types Distribution")
        chart = alt.Chart(df_fuel_counts).mark_bar().encode(
            x=alt.X('Fuel Type', sort='-y', title='Fuel Type'),
            y=alt.Y('Fuel Count', title='Number of Stations'),
            tooltip=['Fuel Type', 'Fuel Count'],
        ).properties(
            width=600,
            height=350
        )
        st.altair_chart(chart, use_container_width=True)

        # navigation buttons
        col1, col2 = st.columns(2)
        with col1:
            # update go back for usability test
            if st.button("Back to Search", key="back_to_search_results"):
                st.session_state.current_step = "Task 1"
                st.rerun()
        with col2:
            if st.button("Receive Search Results: Continue to Task 3", key="receive_search_results"):
                mark_task_end("Task 2")
                st.session_state.task_success["Task 2"] = True
                go_next()
                st.rerun()


    else:
        st.warning("No search results available. Please go back and search again")
        st.session_state.stations = None
        st.session_state.locations = None

        if st.button("Back to Search", key="no_stations_back"):
            st.session_state.current_step = "Task 1"
            st.session_state.task_success["Task 2"] = False
            mark_task_end("Task 2")
            st.rerun()


# receive search results
elif st.session_state.current_step == "Task 3":
    if "Task 3" not in st.session_state.task_start_times:
        mark_task_start("Task 3")
    st.subheader(f"Task 3: Choose How to Receive Your Search Results")

    delivery_method = st.selectbox("How would you like to receive your search results",
                                   ["Email", "Text Message"])

    contact_info = None
    if delivery_method == "Email":
        contact_info = st.text_input("Enter your email address")
    elif delivery_method == "Text Message":
        contact_info = st.text_input("Enter your phone number (with country code).")

    send_clicked = st.button("Send Search Results")

    #initialize to track results were sent
    if "results_sent" not in st.session_state:
        st.session_state.results_sent = False

    if send_clicked:
        if not contact_info or not contact_info.strip():
            st.error(f"Please enter your {delivery_method.lower()}.")
            st.session_state.results_sent = False
        else:
            st.success(f"Search results will be sent to {delivery_method.lower()}. "
                       f"Click Feedback to continue")
            st.session_state.results_sent = True


    if st.button("Feedback"):
        if st.session_state.get("results_sent", False) and contact_info and contact_info.strip():
            mark_task_end("Task 3")
            st.session_state.task_success["Task 3"] = True
            go_next()
            st.rerun()
        else:
            st.error(f"Please send search results before proceeding to feedback.")

# feedback form
elif st.session_state.current_step == "Feedback":
    st.header("Usability Feedback")

    name = st.text_input("Enter your first and last name")
    age = st.slider("Select your age", 18, 80)
    difficulty = st.radio("How difficult was it to navigate through the tasks", ["Easy", "Moderate", "Difficult"])
    feedback = st.text_area("Any suggestions or thoughts on improving the app?")

    if st.button("Submit Feedback"):
        if not name.strip():
            st.error(f"Please enter your first and last name.")
        elif not feedback.strip():
            st.warning(f"We appreciate your feedback! Please provide a suggestion or comment")
        else:
            #data row for google sheets
            row = [
                name,
                age,
                difficulty,
                feedback,
                st.session_state.task_durations.get("Task 1", 0),
                st.session_state.task_durations.get("Task 2", 0),
                st.session_state.task_durations.get("Task 3", 0),
                st.session_state.task_success.get("Task 1", False),
                st.session_state.task_success.get("Task 2", False),
                st.session_state.task_success.get("Task 3", False),
            ]
            # append to google sheets
            try:
                sheet.append_row(row)
                st.success("Feedback submitted. Redirecting.....")
                st.session_state.current_step = "Thank You"
                st.rerun()
            except Exception as e:
                st.error(f"Failed to submit feedback: {e}")

#thank you page
elif st.session_state.current_step == "Thank You":
    st.markdown("""
    Thank You for your completeing the usability test and sharing your feedback. 
    Your input helps us improve the Alternative Fuel Finder experience for everyone.
    You may now close this window.
    """)





