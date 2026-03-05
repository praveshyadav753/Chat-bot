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
    # openai  groq

settings = Settings()
