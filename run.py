import os

from web import create_app

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 5000

WILDCARD_HOST = '0.0.0.0'

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', DEFAULT_PORT))
    host = os.environ.get('FLASK_HOST', DEFAULT_HOST)

    if app.debug and host == WILDCARD_HOST:
        raise RuntimeError(
            "Cannot expose the development debugger on all network interfaces."
        )

    app.run(debug=app.debug, host=host, port=port)
