import os

from web import create_app

app = create_app()

if __name__ == '__main__':
    is_debug = True
    port = int(os.environ.get('FLASK_PORT', 5000))

    app.run(debug=is_debug, host="0.0.0.0", port=port)
