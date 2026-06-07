# Social Media Content Generator API

Flask REST API that stores social media posts in PostgreSQL and can generate structured content with the OpenAI API.

## Features

- PostgreSQL connection using `DATABASE_URL`.
- SQLAlchemy model for `SocialMediaPost`.
- Pydantic schemas for validation and serialization.
- CRUD endpoints for social media content.
- AI generation endpoint that returns structured output and stores it in the database.
- Swagger documentation with examples at `/api/docs`.

## Requirements

- Python 3.9 or newer.
- PostgreSQL database.
- OpenAI API key for the AI generation endpoint.

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

```bash
export DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/social_posts"
export OPENAI_API_KEY="your-openai-api-key"
export OPENAI_MODEL="gpt-4o-mini"
```

`OPENAI_MODEL` is optional. The application defaults to `gpt-4o-mini`.

## Run the API

```bash
python app.py
```

The API starts on `http://localhost:5000`.

Swagger documentation is available at:

```text
http://localhost:5000/api/docs
```

The OpenAPI JSON document is available at:

```text
http://localhost:5000/api/openapi.json
```

## Data Model

`SocialMediaPost` contains:

- `id`: primary key.
- `platform`: social media platform, such as X, LinkedIn, or Facebook.
- `title`: article title or topic.
- `tone`: writing style, such as formal, informal, or humorous.
- `content`: long text content.
- `hashtags`: suggested hashtags.
- `link`: optional external resource.
- `created_at`: automatically generated creation date in the database.

## Endpoints

### List Contents

```bash
curl http://localhost:5000/api/contents
```

### Get Content By ID

```bash
curl http://localhost:5000/api/contents/1
```

### Create Content

```bash
curl -X POST http://localhost:5000/api/contents \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "LinkedIn",
    "title": "AI in Education",
    "tone": "formal",
    "content": "AI can help educators personalize learning and improve student outcomes.",
    "hashtags": ["#AI", "#Education", "#Learning"],
    "link": "https://example.com/ai-education"
  }'
```

### Generate Content With AI

```bash
curl -X POST http://localhost:5000/api/contents/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a LinkedIn post about AI helping small businesses write better content.",
    "platform": "LinkedIn",
    "tone": "formal",
    "link": "https://example.com/ai-content"
  }'
```

### Update Content

```bash
curl -X PUT http://localhost:5000/api/contents/1 \
  -H "Content-Type: application/json" \
  -d '{
    "tone": "humorous",
    "hashtags": ["#AI", "#ContentCreation", "#SocialMedia"]
  }'
```

### Delete Content

```bash
curl -X DELETE http://localhost:5000/api/contents/1
```

## Notes

The table is created automatically at startup with `Base.metadata.create_all(engine)`, which keeps the project simple for local execution and assignment review.
