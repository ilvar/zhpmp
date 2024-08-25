import base64
import os
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram import Bot
from openai import OpenAI

# OpenAI API credentials
openai_api_key = os.environ.get("OPENAI_API_KEY")

# Telegram credentials
telegram_token = os.environ.get("TELEGRAM_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

KDMID_URL = os.environ.get("KDMID_URL")

# Setting up headless Firefox
options = Options()
options.headless = True
driver = webdriver.Firefox(options=options)

def send_telegram_message(message):
    with Bot(telegram_token) as bot:
        bot.send_message(telegram_chat_id, message)

def recognize_captcha(image_data):
    client = OpenAI(api_key=openai_api_key)

    base64_image = base64.b64encode(image_data).decode("utf-8")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "What numbers are this image (return only the number)?"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ],
        }],
        max_tokens=300,
    )
    # Assume that the first recognized text is the correct one.
    return response.choices[0].message.content.replace(" ", "").replace("\n", "")

def main():
    try:
        # Load the page
        driver.get(KDMID_URL)

        # Wait for the CAPTCHA to load and take a screenshot
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "ctl00_MainContent_imgSecNum")))

        solved = False
        i = 0
        while not solved and i < 5:
            captcha_element = driver.find_element(By.ID, "ctl00_MainContent_imgSecNum")
            captcha_screenshot = captcha_element.screenshot_as_png

            # Recognize CAPTCHA using OpenAI API
            captcha_text = recognize_captcha(captcha_screenshot)
            print(f"Recognized CAPTCHA: {captcha_text}")

            # Enter CAPTCHA and click the button
            captcha_input = driver.find_element(By.ID, "ctl00_MainContent_txtCode")
            captcha_input.send_keys(captcha_text)
            submit_button = driver.find_element(By.ID, "ctl00_MainContent_ButtonA")
            submit_button.click()
            print("Submitted the CAPTCHA")

            try:
                # Wait for the next page and check for the button
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "ctl00_MainContent_ButtonB")))
                solved = True
            except Exception:
                i += 1
                captcha_input = driver.find_element(By.ID, "ctl00_MainContent_txtCode")
                captcha_input.clear()
                print("Failed to solve the CAPTCHA, retrying...")

        driver.find_element(By.ID, "ctl00_MainContent_ButtonB").click()
        print("Clicked the button on the second page")

        # Check if the third page contains "sorry"
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print(driver.page_source.lower())
        sorry = "извините, но в настоящий момент на интересующее вас консульское действие в системе предварительной записи нет свободного времени"
        if sorry not in driver.page_source.lower():
            send_telegram_message("The appointment is available!")

    finally:
        driver.quit()
