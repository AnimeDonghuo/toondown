from app.links import extract_urls, filename_from_url, is_safe_http_url, parse_tme, strip_urls


def test_tme_public():
    ref = parse_tme("https://t.me/durov/2")
    assert ref is not None
    assert ref.chat == "durov"
    assert ref.msg_id == 2


def test_tme_private():
    ref = parse_tme("https://t.me/c/1234567890/42")
    assert ref is not None
    assert ref.chat == -1001234567890
    assert ref.msg_id == 42


def test_urls_and_caption():
    text = "My title\nhttps://cdn.example.com/a.mp4\ntag1,tag2"
    urls = extract_urls(text)
    assert urls == ["https://cdn.example.com/a.mp4"]
    assert "My title" in strip_urls(text)


def test_filename_and_ssrf():
    assert filename_from_url("https://x.com/foo/bar.mkv") == "bar.mkv"
    assert is_safe_http_url("https://cdn.example.com/v.mp4")
    assert not is_safe_http_url("http://127.0.0.1/x")
    assert not is_safe_http_url("http://192.168.0.5/x")
