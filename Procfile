release: flask db upgrade && flask seed
web: gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60
