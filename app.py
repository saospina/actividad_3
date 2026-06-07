import json
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from flask import Flask, jsonify, redirect, render_template_string, request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, func
from sqlalchemy.orm import Session, declarative_base, sessionmaker


Base = declarative_base()
SessionLocal = None


class SocialMediaPost(Base):
    __tablename__ = "social_media_posts"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(80), nullable=False)
    title = Column(String(255), nullable=False)
    tone = Column(String(80), nullable=False)
    content = Column(Text, nullable=False)
    hashtags = Column(Text, nullable=False, default="")
    link = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SocialMediaPostBase(BaseModel):
    platform: str = Field(..., min_length=1, max_length=80, examples=["LinkedIn"])
    title: str = Field(..., min_length=1, max_length=255, examples=["AI in Education"])
    tone: str = Field(..., min_length=1, max_length=80, examples=["formal"])
    content: str = Field(..., min_length=1, examples=["Artificial intelligence is changing how teams create content..."])
    hashtags: List[str] = Field(default_factory=list, examples=[["#AI", "#Marketing", "#SocialMedia"]])
    link: Optional[str] = Field(default=None, max_length=500, examples=["https://example.com/article"])

    @field_validator("platform", "title", "tone", "content")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty.")
        return value

    @field_validator("hashtags")
    @classmethod
    def normalize_hashtags(cls, value: List[str]) -> List[str]:
        normalized = []
        for hashtag in value:
            clean_hashtag = hashtag.strip()
            if not clean_hashtag:
                continue
            if not clean_hashtag.startswith("#"):
                clean_hashtag = f"#{clean_hashtag}"
            normalized.append(clean_hashtag)
        return normalized

    @field_validator("link")
    @classmethod
    def strip_optional_link(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SocialMediaPostCreate(SocialMediaPostBase):
    pass


class SocialMediaPostUpdate(BaseModel):
    platform: Optional[str] = Field(default=None, min_length=1, max_length=80)
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    tone: Optional[str] = Field(default=None, min_length=1, max_length=80)
    content: Optional[str] = Field(default=None, min_length=1)
    hashtags: Optional[List[str]] = None
    link: Optional[str] = Field(default=None, max_length=500)

    @field_validator("platform", "title", "tone", "content")
    @classmethod
    def strip_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty.")
        return value

    @field_validator("hashtags")
    @classmethod
    def normalize_optional_hashtags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        return SocialMediaPostBase.normalize_hashtags(value)

    @field_validator("link")
    @classmethod
    def strip_optional_link(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SocialMediaPostSchema(SocialMediaPostBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class SocialMediaPostSchemas(BaseModel):
    contents: List[SocialMediaPostSchema]


class GenerateContentRequest(BaseModel):
    prompt: str = Field(..., min_length=1, examples=["Create a LinkedIn post about using AI to improve online education."])
    platform: Optional[str] = Field(default=None, max_length=80, examples=["LinkedIn"])
    tone: Optional[str] = Field(default=None, max_length=80, examples=["formal"])
    link: Optional[str] = Field(default=None, max_length=500, examples=["https://example.com/resource"])

    @field_validator("prompt")
    @classmethod
    def strip_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Prompt cannot be empty.")
        return value

    @field_validator("platform", "tone", "link")
    @classmethod
    def strip_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return database_url


def configure_database(app: Flask) -> None:
    global SessionLocal

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required.")

    engine = create_engine(normalize_database_url(database_url), pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    app.config["SQLALCHEMY_ENGINE"] = engine


@contextmanager
def get_db_session() -> Session:
    if SessionLocal is None:
        raise RuntimeError("Database has not been configured.")

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def hashtags_to_text(hashtags: List[str]) -> str:
    return json.dumps(hashtags)


def hashtags_from_text(hashtags: Optional[str]) -> List[str]:
    if not hashtags:
        return []
    try:
        value = json.loads(hashtags)
    except json.JSONDecodeError:
        return [item.strip() for item in hashtags.split(",") if item.strip()]
    return value if isinstance(value, list) else []


def post_to_schema(post: SocialMediaPost) -> SocialMediaPostSchema:
    return SocialMediaPostSchema(
        id=post.id,
        platform=post.platform,
        title=post.title,
        tone=post.tone,
        content=post.content,
        hashtags=hashtags_from_text(post.hashtags),
        link=post.link,
        created_at=post.created_at,
    )


def validate_json(schema: Type[BaseModel]) -> BaseModel:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    return schema.model_validate(payload)


def validation_error_response(error: Exception, status_code: int = 400):
    if isinstance(error, ValidationError):
        return jsonify({"error": "Validation error", "details": json.loads(error.json())}), status_code
    return jsonify({"error": str(error)}), status_code


def create_post(db: Session, data: SocialMediaPostCreate) -> SocialMediaPost:
    post = SocialMediaPost(
        platform=data.platform,
        title=data.title,
        tone=data.tone,
        content=data.content,
        hashtags=hashtags_to_text(data.hashtags),
        link=data.link,
    )
    db.add(post)
    db.flush()
    db.refresh(post)
    return post


GENERATED_POST_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "platform": {"type": "string", "description": "Social network where this content should be published."},
        "title": {"type": "string", "description": "Short article title or topic."},
        "tone": {"type": "string", "description": "Writing style, such as formal, informal, or humorous."},
        "content": {"type": "string", "description": "Generated social media post body."},
        "hashtags": {
            "type": "array",
            "description": "Suggested hashtags for the post.",
            "items": {"type": "string"},
        },
        "link": {
            "type": ["string", "null"],
            "description": "External resource URL if one is relevant or provided.",
        },
    },
    "required": ["platform", "title", "tone", "content", "hashtags", "link"],
}


def generate_social_post(request_data: GenerateContentRequest) -> SocialMediaPostCreate:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required for content generation.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is required. Install dependencies from requirements.txt.") from exc

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    hints = {
        "platform": request_data.platform,
        "tone": request_data.tone,
        "link": request_data.link,
    }
    hint_text = "\n".join(f"- {key}: {value}" for key, value in hints.items() if value)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate useful social media content. Return only structured JSON "
                    "that matches the requested schema."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Prompt: {request_data.prompt}\n"
                    f"Optional hints:\n{hint_text or '- none'}\n\n"
                    "Generate one complete social media post."
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "generated_social_media_post",
                "strict": True,
                "schema": GENERATED_POST_JSON_SCHEMA,
            },
        },
    )

    raw_content = completion.choices[0].message.content
    if not raw_content:
        raise RuntimeError("OpenAI returned an empty response.")

    generated_payload = json.loads(raw_content)
    return SocialMediaPostCreate.model_validate(generated_payload)


OPENAPI_SPEC: Dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "Social Media Content Generator API",
        "version": "1.0.0",
        "description": "Flask REST API for creating and AI-generating social media posts.",
    },
    "servers": [{"url": "http://localhost:5000"}],
    "paths": {
        "/api/contents": {
            "get": {
                "summary": "List all social media posts",
                "responses": {
                    "200": {
                        "description": "All social media posts",
                        "content": {
                            "application/json": {
                                "example": {
                                    "contents": [
                                        {
                                            "id": 1,
                                            "platform": "LinkedIn",
                                            "title": "AI in Education",
                                            "tone": "formal",
                                            "content": "AI can help educators personalize learning...",
                                            "hashtags": ["#AI", "#Education"],
                                            "link": "https://example.com/article",
                                            "created_at": "2026-06-06T19:12:00Z",
                                        }
                                    ]
                                }
                            }
                        },
                    }
                },
            },
            "post": {
                "summary": "Create a social media post",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "example": {
                                "platform": "X",
                                "title": "AI Marketing Tips",
                                "tone": "informal",
                                "content": "Try using AI to brainstorm campaign ideas faster.",
                                "hashtags": ["#AI", "#Marketing"],
                                "link": "https://example.com/tips",
                            }
                        }
                    },
                },
                "responses": {"201": {"description": "Created social media post"}},
            },
        },
        "/api/contents/{id}": {
            "get": {
                "summary": "Get one social media post by ID",
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Social media post"}, "404": {"description": "Not found"}},
            },
            "put": {
                "summary": "Update a social media post",
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "example": {
                                "tone": "humorous",
                                "hashtags": ["#AI", "#ContentCreation", "#SocialMedia"],
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Updated social media post"}, "404": {"description": "Not found"}},
            },
            "delete": {
                "summary": "Delete a social media post",
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Deleted"}, "404": {"description": "Not found"}},
            },
        },
        "/api/contents/generate": {
            "post": {
                "summary": "Generate and store a social media post with AI",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "example": {
                                "prompt": "Create a LinkedIn post about AI helping small businesses write better content.",
                                "platform": "LinkedIn",
                                "tone": "formal",
                                "link": "https://example.com/ai-content",
                            }
                        }
                    },
                },
                "responses": {"201": {"description": "Generated and stored social media post"}},
            }
        },
    },
}


SWAGGER_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Social Media Content Generator API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.onload = () => {
        window.ui = SwaggerUIBundle({
          url: "/api/openapi.json",
          dom_id: "#swagger-ui"
        });
      };
    </script>
  </body>
</html>
"""


def create_app() -> Flask:
    app = Flask(__name__)
    configure_database(app)

    @app.errorhandler(RuntimeError)
    def handle_runtime_error(error):
        return jsonify({"error": str(error)}), 500

    @app.errorhandler(404)
    def handle_not_found(_error):
        return jsonify({"error": "Resource not found."}), 404

    @app.get("/")
    def root():
        return redirect("/api/docs")

    @app.get("/api/docs")
    def swagger_docs():
        return render_template_string(SWAGGER_HTML)

    @app.get("/api/openapi.json")
    def openapi_json():
        return jsonify(OPENAPI_SPEC)

    @app.get("/api/contents")
    def get_contents():
        with get_db_session() as db:
            posts = db.query(SocialMediaPost).order_by(SocialMediaPost.created_at.desc()).all()
            response = SocialMediaPostSchemas(contents=[post_to_schema(post) for post in posts])
            return jsonify(response.model_dump(mode="json"))

    @app.get("/api/contents/<int:content_id>")
    def get_content(content_id: int):
        with get_db_session() as db:
            post = db.get(SocialMediaPost, content_id)
            if post is None:
                return jsonify({"error": "Social media post not found."}), 404
            return jsonify(post_to_schema(post).model_dump(mode="json"))

    @app.post("/api/contents")
    def create_content():
        try:
            data = validate_json(SocialMediaPostCreate)
        except (ValidationError, ValueError) as error:
            return validation_error_response(error)

        with get_db_session() as db:
            post = create_post(db, data)
            return jsonify(post_to_schema(post).model_dump(mode="json")), 201

    @app.post("/api/contents/generate")
    def generate_content():
        try:
            data = validate_json(GenerateContentRequest)
            generated_post = generate_social_post(data)
        except (ValidationError, ValueError, json.JSONDecodeError) as error:
            return validation_error_response(error)
        except Exception as error:
            return jsonify({"error": str(error)}), 502

        with get_db_session() as db:
            post = create_post(db, generated_post)
            return jsonify(post_to_schema(post).model_dump(mode="json")), 201

    @app.put("/api/contents/<int:content_id>")
    def update_content(content_id: int):
        try:
            data = validate_json(SocialMediaPostUpdate)
        except (ValidationError, ValueError) as error:
            return validation_error_response(error)

        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return jsonify({"error": "At least one field must be provided for update."}), 400

        with get_db_session() as db:
            post = db.get(SocialMediaPost, content_id)
            if post is None:
                return jsonify({"error": "Social media post not found."}), 404

            for field, value in updates.items():
                if field == "hashtags" and value is not None:
                    setattr(post, field, hashtags_to_text(value))
                else:
                    setattr(post, field, value)

            db.flush()
            db.refresh(post)
            return jsonify(post_to_schema(post).model_dump(mode="json"))

    @app.delete("/api/contents/<int:content_id>")
    def delete_content(content_id: int):
        with get_db_session() as db:
            post = db.get(SocialMediaPost, content_id)
            if post is None:
                return jsonify({"error": "Social media post not found."}), 404

            db.delete(post)
            return jsonify({"message": "Social media post deleted.", "id": content_id})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
