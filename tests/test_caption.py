from app.bili_upload import parse_caption


def test_empty():
    meta = parse_caption(None, "clip.mp4")
    assert meta["title"] == "clip"
    assert meta["tags"] == ""
    assert meta["source"] == ""


def test_full_caption():
    meta = parse_caption(
        "Cool title\nfoo,bar\nhello world\nsource: https://ex.com/a",
        "x.mp4",
    )
    assert meta["title"] == "Cool title"
    assert meta["tags"] == "foo,bar"
    assert "hello world" in meta["desc"]
    assert meta["source"] == "https://ex.com/a"
