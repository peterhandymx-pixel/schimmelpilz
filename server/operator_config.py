"""Load the single-server operator's allowlisted .env values without shell evaluation."""
import os


def load(path):
    allowed={'PUBLIC_APP_URL','PRICE_CURRENCY','PRICE_PERSONAL','PRICE_BUSINESS','PRICE_FIRM','CLIP_LINK_PERSONAL','CLIP_LINK_BUSINESS','CLIP_LINK_FIRM',
             'SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','SMTP_FROM','SMTP_SECURITY','MAIL_OUTBOX_DIR','ADMIN_MFA_REQUIRED','ADMIN_EMAILS','MAILBOX_ALLOW_PRIVATE_HOSTS',
             'AI_PROVIDER','GEMINI_API_KEY','GEMINI_MODEL','GEMINI_BASE_URL','GROQ_API_KEY','GROQ_MODEL','GROQ_BASE_URL','OLLAMA_MODEL','OLLAMA_BASE_URL','PAYMENT_MODE',
             'OPERATOR_NAME','OPERATOR_LEGAL_FORM','OPERATOR_REPRESENTATIVE','OPERATOR_ADDRESS','OPERATOR_EMAIL','OPERATOR_PHONE','OPERATOR_REGISTER',
             'OPERATOR_TAX_ID','OPERATOR_CONTENT_RESPONSIBLE','OPERATOR_HOSTING','OPERATOR_MAIL_PROVIDER'}
    if not path.is_file():return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1);key=key.strip();value=value.strip()
        if key not in allowed:continue
        if len(value)>1 and value[0]==value[-1] and value[0] in {'"',"'"}:value=value[1:-1]
        if value:os.environ.setdefault(key,value)
