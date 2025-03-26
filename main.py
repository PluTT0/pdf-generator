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
load_dotenv()



# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Отримання API-ключів із змінних середовища
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
DOCUMENT_TEMPLATE_ID = os.getenv("DOCUMENT_TEMPLATE_ID")


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
    print('sync done')
except Exception as e:
    logging.error(f"Помилка автентифікації Google API: {e}")
    exit(1)

# Генерація тексту через OpenAI API
def generate_content(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[{"role": "system", "content": "You are an expert content creator."},
                      {"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except openai.OpenAIError as e:
        logging.error(f"Помилка генерації контенту: {e}")
        return ""
    except requests.exceptions.RequestException as e:
        logging.error(f"Проблема з мережею: {e}")
        return ""


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
    except Exception as e:
        print(f"❌ Помилка експорту файлу: {e}")

# Головний процес
def main():
    try:
        topic = "Як ефективно планувати день"
        prompt = f"Створи детальний гайд про {topic} у форматі чек-листа."
        
        content = generate_content(prompt)
        if not content:
            logging.error("Не вдалося створити контент.")
            return
        
        update_response = update_google_doc(DOCUMENT_TEMPLATE_ID, content)
        pdf_response = export_pdf(DOCUMENT_TEMPLATE_ID)
        
        logging.info(update_response)
        logging.info(pdf_response)
    except Exception as e:
        logging.error(f"Помилка виконання програми: {e}")

if __name__ == "__main__":
    main()
