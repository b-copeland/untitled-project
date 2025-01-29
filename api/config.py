import os

class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]
    JWT_ACCESS_LIFESPAN = {'hours': 24}
    JWT_REFRESH_LIFESPAN = {'hours': 24}
    MAIL_SERVER = 'smtp.sendgrid.net'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'apikey'
    MAIL_PASSWORD = os.environ.get('SENDGRID_API_KEY')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    AZURE_FUNCTION_ENDPOINT = os.environ.get('COSMOS_ENDPOINT')
    AZURE_FUNCTION_KEY = os.environ.get('COSMOS_KEY')
    # Initialize a local database for the example
    SQLALCHEMY_DATABASE_URI = os.environ["SQLALCHEMY_DATABASE_URI"]

class TestingConfig(Config):
    SECRET_KEY = os.environ["SECRET_KEY"]
    JWT_ACCESS_LIFESPAN = {'hours': 24}
    JWT_REFRESH_LIFESPAN = {'hours': 24}
    MAIL_SERVER = 'smtp.sendgrid.net'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'apikey'
    MAIL_PASSWORD = os.environ.get('SENDGRID_API_KEY')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    AZURE_FUNCTION_ENDPOINT = os.environ.get('COSMOS_ENDPOINT')
    AZURE_FUNCTION_KEY = os.environ.get('COSMOS_KEY')
    # Initialize a local database for the example
    SQLALCHEMY_DATABASE_URI = "sqlite:///pytest.db"