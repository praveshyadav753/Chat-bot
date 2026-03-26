from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    OPENAI_API_KEY: str = "apikey"
    GEMINI_MODEL:str ="gemini-2.5-flash"
    OPENAI_MODEL :str="gpt-5-nano"
    GROQ_MODEL: str =""
    llm_provider :str ="gemini"  

    SIMILARITY_THRESHOLD : float = 0.75
    TOP_K : int = 8    #for retrival augment
    initial_retrieval_k:int = 20
    max_context_chunks : int =5

    S3_BUCKET:str = "chatbot-bucket-pravesh"
    AWS_REGION:str = "ap-south-1"
    # CELERY_BROKER_URL :str = "redis://redis:6379/0"
    # CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"
    # REDIS_URL :str = "redis://redis:6379/0"

    CELERY_BROKER_URL :str = "rediss://master.chatbot-cluster-disable.cg2xct.aps1.cache.amazonaws.com:6379"
    CELERY_RESULT_BACKEND: str = "rediss://master.chatbot-cluster-disable.cg2xct.aps1.cache.amazonaws.com:6379"
    REDIS_URL :str = "rediss://master.chatbot-cluster-disable.cg2xct.aps1.cache.amazonaws.com:6379"

    # openai  groq
    # CELERY_BROKER_URL :str = "redis://localhost:6379/0"
    # CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    # REDIS_URL :str = "redis://localhost:6379/0"

settings = Settings()
