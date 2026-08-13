from rmstory.discovery import discover


def test_single_file(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("x")
    assert discover([f]) == [f.resolve()]


def test_directory_recursive_by_default(tmp_path):
    (tmp_path / "sub").mkdir()
    top = tmp_path / "a.md"
    top.write_text("x")
    nested = tmp_path / "sub" / "b.html"
    nested.write_text("x")
    ignored = tmp_path / "sub" / "c.txt"
    ignored.write_text("x")

    result = discover([tmp_path])
    assert result == sorted([top.resolve(), nested.resolve()])


def test_directory_non_recursive(tmp_path):
    (tmp_path / "sub").mkdir()
    top = tmp_path / "a.md"
    top.write_text("x")
    (tmp_path / "sub" / "b.md").write_text("x")

    result = discover([tmp_path], recursive=False)
    assert result == [top.resolve()]


def test_lexical_order(tmp_path):
    (tmp_path / "b.md").write_text("x")
    (tmp_path / "a.md").write_text("x")
    result = discover([tmp_path])
    assert result == sorted(result)
