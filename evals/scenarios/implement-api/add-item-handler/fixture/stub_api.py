def add_item_handler(request, store):
    """POST /api/items 핸들러.

    request: {"name": str}
    store: list (인메모리 저장소, append로 추가)
    - "name"이 없거나 빈 문자열이면 400, body={"error": "name required"}
    - 정상이면 store에 {"name": name}을 append하고
      201, body={"id": <추가 전 store 길이>, "name": name} 반환
    """
    raise NotImplementedError
