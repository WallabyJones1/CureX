FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Fail the BUILD if GitHub is missing frontend files (rather than crash at runtime).
RUN python -c "from pathlib import Path; required=['app.py','index.html','app.js','style.css','curex-logo.png','cx-tissue-field.svg','cx-reward-flow.svg','cx-library.svg','governor.py','governor_worker.py','news_scanner.py','bond.py','atlas-topics.json','resources.json','image-library.json']; missing=[x for x in required if not Path(x).is_file()]; assert not missing, 'Missing root files: '+', '.join(missing)"
RUN python -m py_compile app.py governor.py governor_worker.py news_scanner.py bond.py && rm -rf tests
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
EXPOSE 8000
# One worker: rate limits are held in process memory and SQLite prefers a single writer.
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-server-header"]
