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
    # Where storage calls go: 'functionapp' (over HTTP) or 'inprocess' (its handlers in this process, which then needs
    # the function app's COSMOS_* settings). See untitledapp.configure_storage.
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'functionapp')
    # The tick spreads its kingdoms over this many seconds, so its writes do not all land at once (refresh._paced).
    # Keep it well under the minute between ticks.
    TICK_SPREAD_SECONDS = float(os.environ.get('TICK_SPREAD_SECONDS', '30'))

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
    STRICT_KINGDOM_FIELDS = True  # a kingdom write with an unknown field raises instead of dropping it (check_function_url)
    RATELIMIT_ENABLED = False  # tests make hundreds of requests a second from one address
    TICK_SPREAD_SECONDS = 0  # a test's tick runs at once; refresh._paced has its own tests
    FRONTEND_URL = 'http://frontend.test'
    AZURE_FUNCTION_ENDPOINT = "http://localhost:7071/api"
    AZURE_FUNCTION_KEY = ""

class RateLimitTestingConfig(TestingConfig):
    """The tests' config with the rate limits on, for the tests of the limits themselves (tests/test_rate_limits.py)."""
    RATELIMIT_ENABLED = True
