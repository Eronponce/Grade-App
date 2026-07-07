# Grade App — Grades + Turmas Manager

FastAPI backend para gerenciar grades (cursos) e turmas (turmas de alunos).

## Dados

- **Grades**: 7 cursos (ADS 2000-6000, CIA 1000-2000, EGS 1000-3000)
- **Disciplinas**: 385 cursos únicos
- **Turmas**: gerenciadas em SQLite (criação manual ou via agenda)

Todos os dados são armazenados em SQLite (sem dependências de arquivo).

## Setup Local

```bash
pip install -r requirements.txt
python server.py
```

Acessa: `http://localhost:8765`

## Docker Deploy

```bash
docker compose up -d
```

Acessa: `http://localhost:8765` (ou `:8765` no remoto)

## APIs

### Current Status
```bash
curl http://localhost:8765/api/health
```

### Grades
```bash
curl http://localhost:8765/api/grades
curl http://localhost:8765/api/turmas
```

### Config
```bash
curl http://localhost:8765/api/config
curl -X POST http://localhost:8765/api/config -H "Content-Type: application/json" \
  -d '{"current_bimestre": {"year": 2026, "bim": 3}}'
```

### Turmas CRUD
```bash
# List
curl http://localhost:8765/api/turmas

# Create
curl -X POST http://localhost:8765/api/turmas -H "Content-Type: application/json" \
  -d '{"grade_id": "ADS2000", "label": "Turma 2026", "start_year": 2024, "start_bim": 1}'

# Update
curl -X PATCH http://localhost:8765/api/turmas/{turma_id} -H "Content-Type: application/json" \
  -d '{"label": "Turma 2026 - noturno"}'

# Delete
curl -X DELETE http://localhost:8765/api/turmas/{turma_id}
```

### Bootstrap from Agenda
```bash
curl -X POST http://localhost:8765/api/turmas/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"replace": true}'
```

Popula turmas do `data_analysis/agenda_2026.xlsx`.

## Database

SQLite schema:

```
grades (id, nome_completo)
disciplines (codigo, nome, ch_teo, ch_pra, ch_ext, ch_total, modulo, grade_id)
ementas (codigo, ementa)
turmas (id, grade_id, label, start_year, start_bim, source)
config (current_year, current_bim)
```

Editar diretamente:
```bash
sqlite3 grade_lab.db
```

## Migration (XLSX → SQL)

Para re-migrar dados do Google Drive:

```bash
python migrate_to_sql.py
```

(Requer acesso a `G:\Meu Drive\random\grades\`)

## Frontend

Estático em `static/` (HTML + JS + CSS).

## Tests

```bash
pytest tests/
```
