import streamlit as st
import requests
import re
from PIL import Image
import io
import datetime
import pandas as pd
import os
import base64
import dotenv
import json
from google import genai
dotenv.load_dotenv()

gemini_api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_api_key)
MEAL_DELIMITER = "𓇼 ⋆.˚ 𓆉 𓆝 𓆡⋆.˚ 𓇼"

# -----------------------------
# Meal Plan Parsing & Display
# -----------------------------

def parse_meal_sections(day_content):
    sections = {
        "Breakfast": "",
        "Lunch": "",
        "Dinner": "",
        "Snacks": ""
    }
    #looks for a meal heading and then uses the fishie delimiter to determine the eend of the strting 
    meal_pattern = rf"(?i)(Breakfast|Lunch|Dinner|Snacks):\s*(.*?)(?=\s*{re.escape(MEAL_DELIMITER)}|\Z)"
    matches = re.finditer(meal_pattern, day_content, re.DOTALL)
    
    for match in matches:
        meal_type = match.group(1).capitalize()
        content = match.group(2).strip()
        
        if meal_type == "Snack":
            meal_type = "Snacks"
        sections[meal_type] = content
    return sections

def display_collapsible_meal_plan(day_content):
    meal_sections = parse_meal_sections(day_content)
    for meal_type, content in meal_sections.items():
        with st.expander(meal_type):
            if content:
                st.markdown(content)
            else:
                st.write(f"No details found for {meal_type.lower()}.")
    with st.expander("Raw Plan Text"):
        st.markdown(day_content)

def parse_meal_plan_by_day(meal_plan_text):
    daily_plans = {}
    pattern = r"(?i)(DAY\s+\d+[\s:.-]*([A-Za-z]+))\s*(.*?)(?:\s*-=\*=-|$)"
    matches = re.finditer(pattern, meal_plan_text, re.DOTALL)
    for match in matches:
        header = match.group(1).strip()
        day_name = match.group(2).capitalize()
        day_content = match.group(3).strip()
        daily_plans[day_name] = f"{header}{day_content}"
    if not daily_plans:
        daily_plans = {"Full Plan": meal_plan_text}
    return daily_plans

# -----------------------------
# API Call Functions
# -----------------------------

def generate_meal_plan(profile):
    """
    Generates a personalized meal plan using the Google Gemini API.
    """
    

    prompt = (
        f"Generate a personalized 7-day meal plan for a {profile['age']} year old {profile['gender']} "
        f"with weight {profile['weight']}kg, height {profile['height']}cm, activity level {profile['activity']}, "
        f"dietary preferences {', '.join(profile['dietary'])}, and a fitness goal of {profile['fitness_goal']}. "
    )

    if profile['gender'] == "Female" and profile['menstrual_cycle'] != "Not Applicable":
        prompt += (
            f"User is in menstrual cycle phase {profile['menstrual_cycle']} "
            "give suggestions to support hormonal health. "
        )

    if profile['additional_preferences']:
        prompt += f"Additional preferences: {profile['additional_preferences']}. "

    prompt += (
        "Include macronutrient and micronutrient breakdown, hydration tips, and balanced meals for the day. "
        "Format each day clearly with 'DAY X: DAY_NAME' as a header (e.g., 'DAY 1: MONDAY'). "
        "For each day include clearly labeled sections for Breakfast, Lunch, Dinner, and Snacks. "
        "Make sure each meal section starts with 'Breakfast:', 'Lunch:', 'Dinner:', or 'Snacks:' on its own line. "
        "Add this series of special symbols at the end of each day's meal plan '-=*=-'"
        f"After each meal section, add the following special delimiter: {MEAL_DELIMITER}"

    )

    

    try:
        response = client.models.generate_content(
    model='gemini-2.0-flash', contents=prompt)
        meal_plan = response.text
        return meal_plan
    except Exception as e:
        return f"Error: {str(e)}"


def continue_meal_plan(profile, previous_output):
    """
    Request a continuation of the meal plan using the Google Gemini API.
    Uses the previous output as context and asks for the remaining days.
    """
    

    prompt = "Please continue the meal plan from where it left off, providing any missing days and details."

    messages = [
        {"role": "system", "content": "You are a helpful nutrition expert."},
        {"role": "assistant", "content": previous_output},
        {"role": "user", "content": prompt}
    ]

    # Convert messages to the format expected by Gemini
    gemini_prompt = previous_output + "\n" + prompt  # Combine previous output and prompt

    try:
        response = client.models.generate_content(
    model='gemini-2.0-flash', contents=gemini_prompt)
        continuation = response.text
        return continuation
    except Exception as e:
        return f"Error in continuation: {str(e)}"

# UNUSED CODE, WILL UPDATE LATER

def recognize_food(image_data):
    """
    Recognizes food items in an image using the Google Gemini API.
    """
    

    try:
        img = Image.open(io.BytesIO(image_data))
        prompt = "Analyze this food image. Identify the food items present. Provide a nutritional analysis based on the detected items."

        response = client.models.generate_content(
    model='gemini-2.0-flash', contents=prompt)
        analysis_text = response.text

        # Parse the response (this will need refinement based on the actual response format)
        detected_items = extract_detected_items(analysis_text)  # Function to extract detected items
        nutritional_analysis = extract_nutritional_analysis(analysis_text)  # Function to extract analysis

        return {
            "detected_items": detected_items,
            "nutritional_analysis": nutritional_analysis,
            "raw_data": analysis_text  # Include raw response for debugging
        }

    except Exception as e:
        return f"Error in food recognition: {str(e)}"

def extract_detected_items(analysis_text):
    """
    Extracts detected food items from the analysis text.
    This function needs to be adapted based on the format of the Gemini response.
    """
    # Placeholder implementation - replace with actual parsing logic
    if "Foods detected:" in analysis_text:
      items_str = analysis_text.split("Foods detected:")[1].split("\n")[0]
      return [item.strip() for item in items_str.split(",")]
    else:
      return ["No foods detected."]


def extract_nutritional_analysis(analysis_text):
    """
    Extracts nutritional analysis from the analysis text.
    This function needs to be adapted based on the format of the Gemini response.
    """
    # Placeholder implementation - replace with actual parsing logic
    if "Nutritional Analysis:" in analysis_text:
      return analysis_text.split("Nutritional Analysis:")[1]
    else:
      return "No nutritional analysis available."
#END OF UNUSED CODEBLOCK 1

# -----------------------------
# Main Streamlit UI
# -----------------------------
def main():
    st.title("⊹ ࣪ ﹏𓊝﹏𓂁﹏⊹ ࣪ ˖ deniza's 7-day meal planner")

    # Initialize session state variables
    if 'meal_plan' not in st.session_state:
        st.session_state.meal_plan = None
    if 'daily_plans' not in st.session_state:
        st.session_state.daily_plans = {}
    if 'current_day' not in st.session_state:
        st.session_state.current_day = None

    # Sidebar: User Profile Setup
    with st.sidebar:
        st.header("User Profile Setup")
        age = st.number_input("Age", min_value=10, max_value=100, value=20)
        gender = st.selectbox("Gender", ["Female", "Male"])
        weight = st.number_input("Weight (kg)", min_value=30, max_value=200, value=52)
        height = st.number_input("Height (cm)", min_value=100, max_value=250, value=157)
        activity = st.selectbox("Activity Level", ["Sedentary", "Lightly Active", "Active", "Very Active"])
        dietary = st.multiselect("Dietary Preferences", ["Vegan", "Vegetarian", "Halal", "Kosher", "Gluten-Free", "None"])
        menstrual_cycle = "Not Applicable"
        if gender == "Female":
            menstrual_cycle = st.selectbox("Menstrual Cycle Phase", ["Not Applicable", "Follicular", "Ovulatory", "Luteal", "Menstrual"])
        fitness_goal = st.selectbox("Fitness Goals", ["Weight Loss", "Muscle Gain", "Maintenance"])
        additional_preferences = st.text_area("Additional Preferences", "Enter any foods you like/dislike, specific dietary needs, or other preferences here...").strip()

    profile = {
        "age": age,
        "gender": gender,
        "weight": weight,
        "height": height,
        "activity": activity,
        "dietary": dietary if dietary else ["None"],
        "menstrual_cycle": menstrual_cycle,
        "fitness_goal": fitness_goal,
        "additional_preferences": additional_preferences
    }

    st.header("Generate my meals! ")
    if st.button("Generate 7-Day Meal Plan", use_container_width=True):
        if False:
            st.error("Missing Google Gemini API key. Please configure it to generate meal plans.")
        else:
            with st.spinner("Generating meal plan...𓆝 ⋆.."):
                meal_plan = generate_meal_plan(profile)
                # Check if the plan is truncated (e.g., missing "DAY 7:")
                if "DAY 7:" not in meal_plan:
                    continuation = continue_meal_plan(profile, meal_plan)
                    meal_plan += "" + continuation
                st.session_state.meal_plan = meal_plan
                st.session_state.daily_plans = parse_meal_plan_by_day(meal_plan)
                if st.session_state.daily_plans:
                    st.session_state.current_day = list(st.session_state.daily_plans.keys())[0]
                st.success("Meal plan generated!")

    # --- Day Navigation Buttons ---
    if st.session_state.daily_plans:
        st.subheader("Navigate Days")
        days = list(st.session_state.daily_plans.keys())
        cols_per_row = 4
        for i in range(0, len(days), cols_per_row):
            row_days = days[i:i+cols_per_row]
            row_cols = st.columns(len(row_days))
            for j, day_name in enumerate(row_days):
                if row_cols[j].button(day_name, key=f"day_{day_name}", use_container_width=True):
                    st.session_state.current_day = day_name

        if st.session_state.current_day:
            st.markdown(f"### {st.session_state.current_day}'s Meal Plan")
            display_collapsible_meal_plan(st.session_state.daily_plans[st.session_state.current_day])
            with st.expander("View Complete Meal Plan"):
                st.markdown("### Your Complete 7-Day Meal Plan")
                st.write(st.session_state.meal_plan)

# meal pplan history logging implementation, UNUSED CODEBLOCK2


   # # --- Food Recognition & Logging ---
    st.header("Food Recognition & Logging")
    uploaded_file = st.file_uploader("Upload an image of your meal", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Meal", use_column_width=True)
        if st.button("Analyze Food"):
            if False:
                st.error("Google Gemini API key is required for food analysis.")
            else:
                with st.spinner("Analyzing your food..."):
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format=image.format)
                    img_byte_arr = img_byte_arr.getvalue()
                    food_info = recognize_food(img_byte_arr)
                    st.markdown("### Food Analysis Results")
                    if isinstance(food_info, dict):
                        if "detected_items" in food_info:
                            st.subheader("Detected Items")
                            st.write(", ".join(food_info["detected_items"]))
                        if "nutritional_analysis" in food_info:
                            st.subheader("Nutritional Analysis")
                            st.markdown(food_info["nutritional_analysis"])
                        if "raw_data" in food_info:
                            with st.expander("View Raw Data"):
                                st.json(food_info["raw_data"])
                    else:
                        st.error(food_info)
                        #END OF UNUSED CODEBLOCK 2

if __name__ == "__main__":
    main()