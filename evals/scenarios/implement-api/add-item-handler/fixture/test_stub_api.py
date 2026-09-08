from stub_api import add_item_handler


def test_add_item_success():
    store = []
    resp = add_item_handler({"name": "widget"}, store)
    assert resp == {"status": 201, "body": {"id": 0, "name": "widget"}}
    assert store == [{"name": "widget"}]


def test_add_item_second_gets_incrementing_id():
    store = [{"name": "widget"}]
    resp = add_item_handler({"name": "gadget"}, store)
    assert resp["body"]["id"] == 1


def test_add_item_missing_name():
    store = []
    resp = add_item_handler({}, store)
    assert resp["status"] == 400
    assert store == []


def test_add_item_empty_name():
    store = []
    resp = add_item_handler({"name": ""}, store)
    assert resp["status"] == 400
    assert store == []
