from fastapi import FastAPI
from .routes import router

app = FastAPI(title="Podcast Processing API")

# Include the API routes
app.include_router(router)
