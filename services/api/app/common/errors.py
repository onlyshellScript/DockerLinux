from flask import jsonify


def error_response(message, status_code, code=None):
    body = {"error": message}
    if code:
        body["code"] = code
    return jsonify(body), status_code
