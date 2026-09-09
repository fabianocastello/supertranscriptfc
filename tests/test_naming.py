from voxelfc.naming import build_output_stem


def test_pads_episode_number_from_parent_folder_when_file_is_generic():
    assert (
        build_output_stem("audio", "28_20260117 Xadrez Verbal Especial EUA ataca Venezuela")
        == "0028_20260117 Xadrez Verbal Especial EUA ataca Venezuela"
    )


def test_pads_episode_number_already_wide_enough():
    assert (
        build_output_stem("audio", "347_20221215 Michael Malice Christmas Special")
        == "0347_20221215 Michael Malice Christmas Special"
    )


def test_falls_back_to_file_stem_when_no_useful_parent_folder():
    assert build_output_stem("meeting_2026_01_10", "Recordings") == "meeting_2026_01_10"


def test_pads_leading_number_in_file_stem_when_no_parent_pattern():
    assert build_output_stem("7_interview", "Recordings") == "0007_interview"


def test_no_parent_folder_name():
    assert build_output_stem("42_episode", None) == "0042_episode"
