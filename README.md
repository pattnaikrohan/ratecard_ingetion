# ratecard_ingetion

Carrier Rate Card Extraction & Freightify Ingestion Agent — Enterprise PoC for carrier rate card ingestion, master data validation, and Freightify upload sheet generation.

## Architecture

- **Frontend**: React + Vite + TypeScript + Tailwind CSS
- **Backend**: FastAPI (Python) with Azure Document Intelligence & Azure OpenAI

## Local Development

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
