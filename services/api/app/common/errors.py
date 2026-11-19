from flask import jsonify


# Construye una respuesta JSON de error con mensaje y código HTTP; añade el campo code si se proporciona. Devuelve la tupla (response, status_code).
def error_response(message, status_code, code=None):
    body = {"error": message, "message": message}
    if code:
        body["code"] = code
    return jsonify(body), status_code
