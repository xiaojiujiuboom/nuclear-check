# Nuclear Check

Nuclear Knowledge Hub (Streamlit app).

Online:
https://parkour-7xunzs5op9utrf5zojodqr.streamlit.app/

## Gemini 3 Flash (xiaotiangong) config

Set these secrets in Streamlit (`.streamlit/secrets.toml` or Streamlit Cloud Secrets):

```toml
GEMINI_API_KEY = "your-api-key"
GEMINI_BASE_URL = "https://api.xiaotiangong.com"
GEMINI_API_VERSION = "v1beta"
GEMINI_MODEL = "gemini-3-flash-preview"
```

`GEMINI_BASE_URL / GEMINI_API_VERSION / GEMINI_MODEL` are optional now because the app already defaults to these values.

## Local run

```bash
pip install -r requirements.txt
streamlit run app.py
```
