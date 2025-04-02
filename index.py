import openai
import requests
import json
import os
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from dotenv import load_dotenv
from openai import OpenAI
from weasyprint import HTML
from datetime import datetime
from os.path import abspath
load_dotenv()



# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Отримання API-ключів із змінних середовища
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
DOCUMENT_TEMPLATE_ID = os.getenv("DOCUMENT_TEMPLATE_ID")
TEMPLATE_PATH = "templates/template.html"
IMAGE_FOLDER = "generated_images"
SAVE_FOLDER = "generated_pdf"
client = OpenAI(api_key=OPENAI_API_KEY)


if not OPENAI_API_KEY or not SERVICE_ACCOUNT_FILE or not DOCUMENT_TEMPLATE_ID:
    logging.error("Відсутні необхідні змінні середовища. Перевірте налаштування.")
    exit(1)

# Google Docs & Drive API Credentials
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file'
]

# Authenticate Google API
try:
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    docs_service = build('docs', 'v1', credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)
except Exception as e:
    logging.error(f"Помилка автентифікації Google API: {e}")
    exit(1)

# Генерація тексту через OpenAI API
def generate_content(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "You are a professional PDF document generator and structured HTML documents."},
                {"role": "user", "content": f"Generate an HTML template for a PDF document on the topic: {prompt}. HTML should be complete: - Full structure (`<!DOCTYPE html>`, `<html>`, `<head>`, `<body>`) - Beautifully designed header - Tables, lists or blocks for structuring data - Add examples of filling. Do not use CSS frameworks, only basic inline-CSS. Generate text in English."}],
        )
        return response.choices[0].message.content
    except openai.OpenAIError as e:
        logging.error(f"Помилка генерації контенту: {e}")
        return ""
    except requests.exceptions.RequestException as e:
        logging.error(f"Проблема з мережею: {e}")
        return ""

# Генерація зображення через OpenAI DALL·E
def generate_image(prompt):
    if not os.path.exists(IMAGE_FOLDER):
        os.makedirs(IMAGE_FOLDER)
    try:
        # Генерація зображення
        response = client.images.generate(prompt=prompt, model="dall-e-3", size="1024x1024", n=1)
        image_url = response.data[0].url

        # Завантажуємо зображення
        image_data = requests.get(image_url).content
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        image_path = os.path.join(IMAGE_FOLDER, f"image_{timestamp}.svg")

        with open(image_path, "wb") as file:
            file.write(image_data)

        print(f"✅ Зображення збережено: {image_path}")
        return image_path
    except Exception as e:
        print(f"❌ Помилка генерації зображення: {e}")
        return None

# Оновлення Google Docs з текстом
def update_google_doc(doc_id, content):
    try:
        requests = [{
            'insertText': {
                'location': {'index': 1},
                'text': content
            }
        }]
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        return f"Google Doc Updated: https://docs.google.com/document/d/{doc_id}/edit"
    except Exception as e:
        logging.error(f"Помилка оновлення Google Docs: {e}")
        return ""

# Експорт у PDF з Google Docs
def export_pdf(doc_id):
    pdf_file = f"output_{doc_id}.pdf"
    try:
        request = drive_service.files().export_media(fileId=doc_id, mimeType='application/pdf')
        with open(f"output_{doc_id}.pdf", "wb") as pdf_file:
            pdf_file.write(request.execute())
        print("✅ Файл експортовано успішно.")

        # Видаляємо файл після використання
        """ if os.path.exists(pdf_file):
            os.remove(pdf_file)
            print(f"🗑 Файл {pdf_file} було автоматично видалено.")
        else:
            print("⚠ Файл для видалення не знайдено.") """
    except Exception as e:
        print(f"❌ Помилка експорту файлу: {e}")


def generate_pdf(content, image_path):
    """
    Генерує PDF з текстом та зображенням.
    :param content: Текст для вставки у PDF.
    :param image_path: Шлях до зображення.
    """
    try:
        if not os.path.exists(TEMPLATE_PATH):
            raise FileNotFoundError(f"❌ Шаблон HTML не знайдено: {TEMPLATE_PATH}")

        with open(TEMPLATE_PATH, "r", encoding="utf-8") as file:
            html_template = file.read()

        # Замінюємо {content} у шаблоні на текст
        final_html = html_template.replace("{content}", content)

        # Перевіряємо існування зображення
        if image_path and os.path.exists(image_path):
            image_abs_path = abspath(image_path)
            image_tag = f'<img src="{image_abs_path}" alt="Generated Image" style="width:100%;">'
            final_html = final_html.replace("{image}", image_tag)
        else:
            final_html = final_html.replace("{image}", "")

        # Генеруємо ім'я файлу
        if not os.path.exists(SAVE_FOLDER):
            os.makedirs(SAVE_FOLDER)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_pdf = os.path.join(SAVE_FOLDER, f"report_{timestamp}.pdf")
        print(type(final_html))
        # Генеруємо PDF
        HTML(string=content).write_pdf(output_pdf)
        logging.info(f"✅ PDF згенеровано: {output_pdf}")
        return output_pdf
    except Exception as e:
        logging.error(f"❌ Помилка генерації PDF: {e}")
        return None


# Створення PDF із HTML через WeasyPrint
def generate_pdf_with_weasyprint(html_content, output_filename="local_output.pdf"):
    try:
        HTML(string=html_content).write_pdf(output_filename)
        logging.info(f"✅ PDF (локальний) збережено як {output_filename}")
        return output_filename
    except Exception as e:
        logging.error(f"❌ Помилка генерації локального PDF: {e}")
        return None


def main():
    """
    Основна функція для тесту: створює PDF з готовим текстом та зображенням.
    """
    try:
        #topic = "Як ефективно планувати день"
        #content = "Це тестовий контент для генерації PDF. Використовується для перевірки."
        image_path = "./generated_images/img.svg"
        prompt = f"Таблиця звичок (дата + виконано/не виконано)"
        #image_prompt = "An illustration of a person planning their daily tasks in a modern workspace"
        
        # Генерація контенту
        content = generate_content(prompt)
        new_content = content.replace("```html", "").replace("```", "")
        print(new_content)
        if not content:
            logging.error("Не вдалося створити контент.")
            return
        
        if not os.path.exists(image_path):
            logging.warning(f"⚠ Зображення не знайдено: {image_path}. Буде створено PDF без зображення.")

        pdf_path = generate_pdf(content=new_content, image_path=image_path)
        pdf_two = generate_pdf_with_weasyprint(new_content, output_filename="local_output.pdf")

        if pdf_path:
            logging.info(f"📄 Файл збережено: {pdf_path}")
            logging.info(f"📄 Файл збережено: {pdf_two}")
        else:
            logging.error("❌ Не вдалося створити PDF.")
    except Exception as e:
        logging.error(f"❌ Помилка виконання програми: {e}")

# Головний процес
'''def main():
    try:
        topic = "Як ефективно планувати день"
        prompt = f"Створи детальний гайд про {topic} у форматі чек-листа."
        image_prompt = "An illustration of a person planning their daily tasks in a modern workspace"
        
        # Генерація контенту
        content = generate_content(prompt)
        print(content)
        if not content:
            logging.error("Не вдалося створити контент.")
            return
        
        # Генерація зображення
        image_file = generate_image(image_prompt)
        if not image_file:
            return

        update_response = update_google_doc(DOCUMENT_TEMPLATE_ID, content)
        pdf_response = export_pdf(DOCUMENT_TEMPLATE_ID)

        # Тепер передаємо image_file в generate_pdf
        generate_pdf(content=content, image_path=image_file)  # Викликаємо з image_path

        logging.info(update_response)
        logging.info(f"📄 Google Docs PDF: {pdf_response}")
    except Exception as e:
        logging.error(f"Помилка виконання програми: {e}")'''

if __name__ == "__main__":
    main()
