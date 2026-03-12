# AI Chat Chainlit

Applicazione chat basata su **Chainlit** con:

- chat testuale
- input audio con trascrizione Whisper
- tool LangChain (utility + web search)
- integrazione opzionale **Tavily** per ricerca web
- autenticazione email/password su tabella `users`
- persistenza via SQLAlchemy + storage S3

---

## Indice

- [Panoramica](#panoramica)
- [Struttura progetto](#struttura-progetto)
- [Prerequisiti](#prerequisiti)
- [Download del progetto](#download-del-progetto)
- [Configurazione ambiente (.env)](#configurazione-ambiente-env)
- [Installazione dipendenze](#installazione-dipendenze)
- [Avvio in locale](#avvio-in-locale)
- [Avvio pubblico con ngrok](#avvio-pubblico-con-ngrok)
- [File traffic-policy.yml (ngrok)](#file-traffic-policyyml-ngrok)
- [Integrazione Tavily](#integrazione-tavily)
- [Script amministrativi utenti/password](#script-amministrativi-utentipassword)
- [Troubleshooting](#troubleshooting)
- [Licenza e Changelog](#licenza-e-changelog)

---

## Panoramica

Entry point: `app.py`.

Componenti principali:

- `app.py`: avvio Chainlit, callback chat/audio, autenticazione password, data layer
- `chat_utils/openai_provider.py`: provider modello OpenAI
- `chat_utils/tools.py`: tool custom + caricamento Tavily se disponibile
- `scripts/create_user.py`: creazione/aggiornamento utente
- `scripts/update_password.py`: aggiornamento password
- `traffic-policy.yml`: policy header per traffico dietro ngrok

---

## Struttura progetto

```text
app.py
chainlit.md
README.md
requirements.txt
traffic-policy.yml
chat_utils/
	openai_provider.py
	prompts.py
	tools.py
scripts/
	create_user.py
	update_password.py
public/
```

---

## Prerequisiti

- Python 3.10+ (consigliato 3.11)
- `pip`
- account OpenAI + API key
- database PostgreSQL/Supabase
- bucket S3 compatibile (se usi storage file)
- ngrok (solo se vuoi esporre l’app pubblicamente)

---

## Download del progetto

### Opzione A - Clone Git

```bash
git clone <REPO_URL>
cd ai-chat-chainlit
```

### Opzione B - ZIP

1. Scarica il file ZIP del repository
2. Estrai in una cartella locale
3. Apri la cartella in VS Code

---

## Configurazione ambiente (.env)

Crea un file `.env` nella root del progetto:

```env
# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Tavily (opzionale, abilita web search tool)
TAVILY_API_KEY=your_tavily_api_key

# Database
SUPABASE_DATABASE_URL=postgresql://user:password@host:5432/dbname
PASSWORD_HASH_ITERATIONS=600000

# Storage S3
BUCKET_NAME=your_bucket
AWS_ENDPOINT=https://your-s3-endpoint
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=eu-west-1

# App
MAX_MESSAGES=30
```

Note:

- Se `SUPABASE_DATABASE_URL` manca, l’autenticazione password non è disponibile.
- `PASSWORD_HASH_ITERATIONS` controlla la robustezza PBKDF2.
- Se `TAVILY_API_KEY` non è impostata, il tool Tavily non viene caricato.

---

## Installazione dipendenze

```bash
python -m venv .venv
```

### Attivazione virtualenv

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Windows CMD:

```cmd
.venv\Scripts\activate.bat
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Installa requirements:

```bash
pip install -r requirements.txt
```

---

## Avvio in locale

```bash
chainlit run app.py -w --port 8000
```

Poi apri:

`http://localhost:8000`

---

## Avvio pubblico con ngrok

1. Avvia l’app in locale sulla porta 8000

```bash
chainlit run app.py -w --port 8000
```

2. In un secondo terminale avvia ngrok:

```bash
ngrok http 8000 --traffic-policy-file traffic-policy.yml
```

3. Usa l’URL `https://...ngrok-free.app` generato da ngrok.

---

## File traffic-policy.yml (ngrok)

Il file `traffic-policy.yml` aggiunge l’header:

```yaml
x-ngrok-proxy: "enabled"
```

Serve per identificare/routare correttamente richieste passate da ngrok quando usi policy o integrazioni che richiedono header custom.

Comando consigliato:

```bash
ngrok http 8000 --traffic-policy-file traffic-policy.yml
```

---

## Integrazione Tavily

Nel file `chat_utils/tools.py`, Tavily viene caricato **solo** se esiste `TAVILY_API_KEY` nell’ambiente.

In pratica:

- con `TAVILY_API_KEY` impostata → tool Tavily attivo
- senza `TAVILY_API_KEY` → app funziona comunque, ma senza ricerca Tavily

Verifica rapida variabile:

PowerShell:

```powershell
echo $env:TAVILY_API_KEY
```

Se vuota, aggiungila nel `.env` e riavvia l’app.

---

## Script amministrativi utenti/password

Gli script usano `SUPABASE_DATABASE_URL` e salvano password come hash PBKDF2 SHA-256.

### 1) Creare utente

```bash
python scripts/create_user.py --identifier user@example.com --password "Password123!"
```

Aggiornare utente esistente:

```bash
python scripts/create_user.py --identifier user@example.com --password "Password123!" --update-existing
```

Con ruolo personalizzato:

```bash
python scripts/create_user.py --identifier user@example.com --password "Password123!" --role admin --update-existing
```

### 2) Modificare password utente

```bash
python scripts/update_password.py --identifier user@example.com --password "NuovaPassword123!"
```

Con iterazioni custom:

```bash
python scripts/update_password.py --identifier user@example.com --password "NuovaPassword123!" --iterations 700000
```

---

## Troubleshooting

- `SUPABASE_DATABASE_URL non impostata`: configura `.env`.
- Tavily non disponibile: verifica `TAVILY_API_KEY`.
- ngrok non applica policy: usa `--traffic-policy-file traffic-policy.yml`.
- `chainlit ... -h` può fallire in alcuni contesti; prova `chainlit --help` o `chainlit run --help`.
- errori DB: controlla URL PostgreSQL e connettività di rete.
- errori S3: verifica bucket/endpoint/credenziali/regione.

---

## Comandi rapidi

```bash
# install
pip install -r requirements.txt

# run locale
chainlit run app.py -w --port 8000

# run pubblico con ngrok + policy
ngrok http 8000 --traffic-policy-file traffic-policy.yml

# crea utente
python scripts/create_user.py --identifier user@example.com --password "Password123!"

# cambia password
python scripts/update_password.py --identifier user@example.com --password "NuovaPassword123!"
```
---

## Licenza e Changelog

- Licenza progetto: [LICENSE](LICENSE)
- Storico modifiche: [CHANGELOG.md](CHANGELOG.md)
