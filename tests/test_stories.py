from rmstory.storage import stories


def test_merge_appends_new_ids_preserving_existing_order(tmp_path):
    result = stories.merge(tmp_path, "villain-arc", ["b", "a", "c"])
    assert result.added == ["b", "a", "c"]
    assert stories.load(tmp_path, "villain-arc") == ["b", "a", "c"]

    # Re-running with a reshuffled discovery order must not reorder
    # existing entries -- only append genuinely new ones.
    result2 = stories.merge(tmp_path, "villain-arc", ["c", "a", "b", "d"])
    assert result2.added == ["d"]
    assert stories.load(tmp_path, "villain-arc") == ["b", "a", "c", "d"]


def test_merge_flags_missing_without_deleting(tmp_path):
    stories.merge(tmp_path, "villain-arc", ["a", "b"])
    result = stories.merge(tmp_path, "villain-arc", ["a"])
    assert result.missing == ["b"]
    assert stories.load(tmp_path, "villain-arc") == ["a", "b"]  # not removed


def test_prune_removes_only_when_called(tmp_path):
    stories.merge(tmp_path, "villain-arc", ["a", "b"])
    removed = stories.prune(tmp_path, "villain-arc", ["a"])
    assert removed == ["b"]
    assert stories.load(tmp_path, "villain-arc") == ["a"]
