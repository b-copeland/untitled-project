import logging
from untitledapp import create_app

app = create_app()

if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.glogging.Logger')
    gunicorn_error_handlers = logging.getLogger('gunicorn.error').handlers
    gunicorn_access_handlers = logging.getLogger('gunicorn.access').handlers
    app.logger.handlers.extend(gunicorn_logger.handlers)
    app.logger.handlers.extend(gunicorn_error_handlers)
    app.logger.handlers.extend(gunicorn_access_handlers)
    app.logger.setLevel(gunicorn_logger.level)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
