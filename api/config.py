import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_ACCESS_LIFESPAN = {'hours': 24}
    JWT_REFRESH_LIFESPAN = {'hours': 24}
    MAIL_SERVER = 'smtp.sendgrid.net'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'apikey'
    MAIL_PASSWORD = os.environ.get('SENDGRID_API_KEY')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND')  # smtp, console or memory; see untitledapp/mailer.py
    FRONTEND_URL = os.environ.get('FRONTEND_URL')  # base of the links in emails; defaults to the request's host
    AZURE_FUNCTION_ENDPOINT = os.environ.get('AZURE_FUNCTION_ENDPOINT')
    AZURE_FUNCTION_KEY = os.environ.get('AZURE_FUNCTIONS_HOST_KEY')
    # Initialize a local database for the example
    SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI")

class TestingConfig(Config):
    SECRET_KEY="12345"
    JWT_ACCESS_LIFESPAN = {'hours': 24}
    JWT_REFRESH_LIFESPAN = {'hours': 24}
    MAIL_SERVER = 'smtp.sendgrid.net'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'apikey'
    MAIL_PASSWORD = os.environ.get('SENDGRID_API_KEY')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    EMAIL_BACKEND = 'memory'
    FRONTEND_URL = 'http://frontend.test'
    AZURE_FUNCTION_ENDPOINT = "http://localhost:7071/api"
    AZURE_FUNCTION_KEY = ""
    # Initialize a local database for the example
    SQLALCHEMY_DATABASE_URI = "sqlite:///pytest.db"