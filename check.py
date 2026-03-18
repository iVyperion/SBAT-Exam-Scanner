import os
import time
from datetime import datetime
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import telebot

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load env
load_dotenv()
EMAIL = os.getenv("SBAT_EMAIL")
PASSWORD = os.getenv("SBAT_PASSWORD")

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

INTERVAL = int(os.getenv("CHECK_INTERVAL", 600))
EXAM_CENTER = os.getenv("EXAM_CENTER", "BRAKEL")


print("SBAT_EMAIL:", EMAIL)
print("SBAT_PASSWORD:", PASSWORD)
print("TELEGRAM_TOKEN:", TOKEN)
print("TELEGRAM_CHAT_ID:", CHAT_ID)
print("EMAIL_SENDER:", os.getenv("EMAIL_SENDER"))
print("EMAIL_RECEIVER:", os.getenv("EMAIL_RECEIVER"))

bot = telebot.TeleBot(TOKEN)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def send_email(subject, message):
    try:
        sender = os.getenv("EMAIL_SENDER")
        password = os.getenv("EMAIL_PASSWORD")
        receiver = os.getenv("EMAIL_RECEIVER")
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = int(os.getenv("SMTP_PORT", 465))

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = receiver
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(sender, password)
        server.send_message(msg)
        server.quit()

        log("Email sent")

    except Exception as e:
        log(f"Email error: {e}")


def notify(msg):
    # Telegram
    try:
        bot.send_message(CHAT_ID, msg)
    except Exception as e:
        log(f"Telegram error: {e}")

    # Email (always on)
    send_email("SBAT Slot Alert 🚨", msg)


def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # IMPORTANT: point to chromium binary
    options.binary_location = "/usr/bin/chromium"

    return webdriver.Chrome(options=options)

def login(driver):
    log("Logging in...")
    driver.get("https://rijbewijs.sbat.be/praktijk/examen/login")

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="E-mail"]'))
    ).send_keys(EMAIL)

    driver.find_element(By.CSS_SELECTOR, 'input[placeholder="Wachtwoord"]').send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, 'button.v-btn.primary').click()

    WebDriverWait(driver, 20).until(
        EC.url_changes("https://rijbewijs.sbat.be/praktijk/examen/login")
    )

    log("Logged in")


def select_dropdown(driver, label, option):
    dropdown = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((
            By.XPATH,
            f"//label[contains(text(), '{label}')]/ancestor::div[contains(@class, 'v-input')]"
        ))
    )
    dropdown.click()
    time.sleep(1)

    el = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((
            By.XPATH,
            f"//div[contains(@class,'v-list-item__title') and contains(text(), '{option}')]"
        ))
    )
    el.click()
    time.sleep(1)


def go_to_calendar(driver):
    driver.get("https://rijbewijs.sbat.be/praktijk/examen/exam")
    time.sleep(4)

    select_dropdown(driver, "Examencentrum", EXAM_CENTER)
    select_dropdown(driver, "Type rijbewijs", "B - Personenauto")
    select_dropdown(driver, "Voertuig", "Eigen voertuig")

    driver.find_element(
        By.XPATH,
        "//button[contains(., 'Volgende')]"
    ).click()


def check_dates(driver, months=6):
    dates = []

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "v-date-picker-table"))
    )

    for _ in range(months):
        header = driver.find_element(By.CLASS_NAME, "v-date-picker-header__value").text
        buttons = driver.find_elements(By.CSS_SELECTOR, ".v-date-picker-table button")

        for b in buttons:
            if not b.get_attribute("disabled"):
                dates.append(f"{b.text} {header}")

        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Next month"]')
            if next_btn.is_enabled():
                next_btn.click()
                time.sleep(2)
            else:
                break
        except:
            break

    return dates


def main():
    driver = create_driver()
    last_seen = set()

    try:
        login(driver)

        while True:
            try:
                log("Checking slots...")

                go_to_calendar(driver)
                dates = check_dates(driver)

                # Only notify if there are NEW slots
                new_dates = set(dates) - last_seen

                if new_dates:
                    msg = "🚨 AVAILABLE SLOTS:\n" + "\n".join(sorted(new_dates))
                    log(msg)
                    notify(msg)
                    last_seen.update(new_dates)

            except Exception as e:
                log(f"Error: {e}")
                log("Re-logging...")
                try:
                    driver.quit()
                except:
                    pass

                driver = create_driver()
                login(driver)

            time.sleep(INTERVAL)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
