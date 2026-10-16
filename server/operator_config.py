"""Load the single-server operator's allowlisted .env values without shell evaluation."""
import os


def load(path):
    allowed={'PUBLIC_APP_URL','STRIPE_SECRET_KEY','STRIPE_WEBHOOK_SECRET','STRIPE_PRICE_PERSONAL','STRIPE_PRICE_BUSINESS','STRIPE_PRICE_FIRM'}
    if not path.is_file():return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1);key=key.strip();value=value.strip()
        if key not in allowed:continue
        if len(value)>1 and value[0]==value[-1] and value[0] in {'"',"'"}:value=value[1:-1]
        if value:os.environ.setdefault(key,value)
