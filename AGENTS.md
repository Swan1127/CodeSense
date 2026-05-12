# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

CodeSense 酷森思 is an intelligent programming education platform for universities. It uses a "Causal Sandbox" for code execution and "Heuristic LLM" for AI-powered programming guidance that leads students to answers through questioning rather than providing direct solutions.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python run.py
# or
python app.py

# Run tests
python -m pytest tests/test_app.py
# or
python tests/test_app.py

# Initialize database (in Python shell)
from models import db, app
with app.app_context():
    db.create_all()

# Production deployment
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

## Architecture

### Application Entry Point
- `app.py` - Main application factory (`create_app()`), registers blueprints, initializes models and async tasks
- `run.py` - Simple wrapper that imports and runs `app.py`
- `wsgi.py` - Production WSGI entry point

### Configuration
- `config.py` - Config class with three environments: `development`, `testing`, `production`
  - Database: `DATABASE_URL` env var (MySQL in production, SQLite in development)
  - AI APIs: `ZHIPU_API_KEY` and/or `OPENAI_API_KEY`
  - `LOAD_LOCAL_MODEL=False` for cloud deployments (saves ~1GB memory)

### Blueprints (Routes)
| Blueprint | Purpose |
|-----------|---------|
| `routes/auth.py` | Login, logout, registration |
| `routes/main.py` | Main pages (home, about, help) |
| `routes/assignments.py` | Assignment CRUD operations |
| `routes/users.py` | User profile management |
| `routes/classes.py` | Class management for teachers |
| `routes/api.py` | REST API for code submission, AI evaluation, ability scoring |

### Core Services (`utils/`)
- `code_evaluator.py` - CodeBERT embedding + TextCNN scoring, initializes local ML models
- `sandbox_runner.py` - subprocess-based code execution sandbox with timeout
- `llm_evaluator.py` - GLM-4/GPT-4 API calls for code evaluation
- `guidance_generator.py` - Heuristic prompts that guide students through questioning
- `code_advisor.py` - Code advice and feedback generation
- `async_tasks.py` - ThreadPool-based async task queue with SSE streaming
- `ability_scorer.py` - Bayesian-weighted ability tracking across 13 C programming concepts
- `prompts.py` - Prompt templates for AI interactions

### Models (`models/`)
- `CNN.py` - TextCNN model using CodeBERT embeddings
- `codebert.py` - CodeBERT model wrapper
- `codebertcnn.pth` - Pretrained weights

### Key Patterns
1. **AI-only mode**: Set `LOAD_LOCAL_MODEL=False` to skip PyTorch model loading
2. **Async evaluation**: Code submissions go through `async_tasks.py` with SSE progress updates
3. **Sandbox security**: 15s compile timeout, 5s run timeout, subprocess isolation
4. **Session management**: Flask-Session with filesystem backend

## Database

SQLAlchemy ORM with models in `models.py`. Uses Flask-Migrate for schema migrations. Key models: User (with usertype: 学生/教师/管理员), Assignment, Submission, Class, AbilityScore.

## Frontend

Bootstrap 5 + Monaco Editor for code editing. Jinja2 templates in `templates/`. Static assets in `static/` with CSS, JS, and images.
