import os

from web import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 5000))
    host = os.environ.get('FLASK_HOST', '127.0.0.1')

    if app.debug and host == '0.0.0.0':
        raise RuntimeError(
            "Cannot expose the development debugger on all network interfaces."
        )

    app.run(debug=app.debug, host=host, port=port)
