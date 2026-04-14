from imap_tools import MailBox, AND
from pypdf import PdfReader, PdfWriter
import io
import anthropic
from pypdf import PdfReader, PdfWriter
from dotenv import load_dotenv
import os
import json
import psycopg2
from datetime import datetime

load_dotenv()


PASSWORD = os.getenv("APP_PASSWORD")
EMAIL = os.getenv("EMAIL")
FOLDER = "/Users/remyfernando/desktop/Noguchi Active/tradewind payslips/26:27"


def extract_pdf_text(reader):
    """Extract text from all pages of a PDF.

    Args:
        reader: pypdf PdfReader object
    Returns:
        str: concatenated text from all pages
    """
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def get_data_from_pdf(reader):
    """Extract structured payslip data from a PDF using the Claude API.

    Args:
        reader: pypdf PdfReader object
    Returns:
        dict: payslip fields including client, net_pay, tax_year, period, date
    """
    text = extract_pdf_text(reader)
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": f"""Extract the following from this payslip and return as JSON only:
    - client
    - net_pay 
    - tax_year
    - period
    - date

    - net_pay should be a number only, no currency symbol
    Payslip:
    {text}"""
            }
        ]
    )

    raw = response.content[0].text
    clean = raw.strip().removeprefix("```json").removesuffix("```")
    data = json.loads(clean)
    return data

def parse_payslip(data):
    """Clean and transform raw LLM payslip data into DB-ready types.

    Args:
        data: dict of raw payslip fields from get_data_from_pdf
    Returns:
        dict: payslip fields with correct Python types for DB insertion
    """
    return {
        'client': data['client'],
        'net_pay': float(data['net_pay']),
        'tax_year': data['tax_year'],
        'period': int(data['period'].split()[1]),
        'date': datetime.strptime(data['date'], '%d/%m/%Y').strftime('%Y-%m-%d')
    }

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def insert_data(data):
    """Insert parsed payslip data into the tracking.payslips table.

    Args:
        data: dict of cleaned payslip fields from parse_payslip
    Returns:
        None. Skips insert if record already exists (client, tax_year, period).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO tracking.payslips
       (client, net_pay, tax_year, period, date)
       VALUES (%s, %s, %s, %s, %s)
       ON CONFLICT (client, tax_year, period) DO NOTHING
       """, (data['client'], data['net_pay'], data['tax_year'], data['period'], data['date'])
    )
    conn.commit()
    conn.close()

def save_payslip(payslip_object, payslip_data, folder_path):
    """Save a decrypted PDF payslip to disk.

    Args:
        payslip_object: pypdf PdfReader object (decrypted)
        payslip_data: dict of parsed payslip fields (used for filename)
        folder_path: str path to destination folder
    Returns:
        None. Saves file as tradewind_{period}.pdf in folder_path.
    """
    writer = PdfWriter()
    for page in payslip_object.pages:
        writer.add_page(page)
    with open(f"{folder_path}/tradewind_{payslip_data['period']}.pdf", "wb") as f:
        writer.write(f)

def process_attachment(att):
    """Decrypt, parse and store a single payslip PDF attachment.

     Args:
         att: imap_tools attachment object containing payload and filename
     Returns:
         None. Saves decrypted PDF to disk and inserts data into DB.
     Raises:
         Exception: if LLM extraction fails after 3 attempts
     """
    pdf_bytes = io.BytesIO(att.payload)
    reader = PdfReader(pdf_bytes)
    reader.decrypt(os.getenv("PDF_PASSWORD"))

    payslip_data = None
    for attempt in range(3):
        try:
            payslip_data = get_data_from_pdf(reader)
            break
        except Exception as e:
            if attempt == 2:
                raise
            print(f" Attempt {attempt + 1} failed: {e}, retrying...")

    p = parse_payslip(payslip_data)
    save_payslip(reader, p, FOLDER)
    insert_data(p)


def main():
    with MailBox('imap.mail.me.com').login(EMAIL, PASSWORD) as mb:
        for msg in mb.fetch(AND(from_="payroll@twrecruitment.com")):
            try:
                if msg.attachments:
                    for att in msg.attachments:
                        process_attachment(att)

            except Exception as e:
                print(f"Failed {msg.subject}: {e}")
                continue

if __name__ == "__main__":
    main()