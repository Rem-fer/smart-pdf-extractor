# Payslip Processing Pipeline
 
Automated pipeline that fetches payslip PDFs from iCloud Mail, decrypts them, extracts key data using the Claude API, and stores results in PostgreSQL.
 
## Features
 
- Fetches payslip attachments via IMAP
- Decrypts password-protected PDFs in memory
- Extracts structured data (client, net pay, tax year, period, date) using Claude AI
- Saves decrypted PDFs to disk
- Inserts data into PostgreSQL with duplicate protection
- Easily adaptable for other structured PDF documents (invoices, contracts, etc.) by updating the LLM prompt
 
## Setup
 
1. Clone the repo
2. Create and activate a virtual environment
3. Install dependencies:
   ```bash
   pip install pypdf imap-tools anthropic psycopg2-binary python-dotenv
   ```
4. Copy `.env.example` to `.env` and fill in your credentials
 
## Environment Variables
 
```
ANTHROPIC_API_KEY=your-api-key
EMAIL=your-icloud-email
PASSWORD=your-app-specific-password
DB_URL=your-postgresql-connection-string
```
 
> **Note:** iCloud requires an app-specific password, not your Apple ID password. Generate one at [appleid.apple.com](https://appleid.apple.com).
 
## Database
 
Create the payslips table in PostgreSQL:
 
```sql
CREATE TABLE tracking.payslips (
    id SERIAL PRIMARY KEY,
    client VARCHAR(255),
    net_pay NUMERIC(10, 2),
    tax_year VARCHAR(10),
    period INTEGER,
    date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);
 
ALTER TABLE tracking.payslips 
ADD CONSTRAINT unique_payslip UNIQUE (client, tax_year, period);
```
 
## Usage
 
```bash
python main.py
```
 
## Project Structure
 
```
├── main.py        # All pipeline logic
├── .env           # Credentials (not committed)
├── .env.example   # Template for environment variables
└── .gitignore
```