def divide_handler(request):
    """POST /api/divide 핸들러.

    request: {"a": number, "b": number}
    반환: {"status": int, "body": dict}
    - a 또는 b가 없으면 400, body={"error": "a and b required"}
    - b == 0 이면 400, body={"error": "division by zero"}
    - 정상이면 200, body={"result": a / b}
    """
    a = request.get("a")
    b = request.get("b")
    if a is None or b is None:
        return {"status": 400, "body": {"error": "a and b required"}}
    if b == 0:
        return {"status": 400, "body": {"error": "division by zero"}}
    return {"status": 200, "body": {"result": a / b}}
