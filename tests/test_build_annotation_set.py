from extraction.build_annotation_set import post_url


def test_post_url_from_db_id_strips_at():
    assert post_url("tg:@O_Arestovich_official:20") == "https://t.me/O_Arestovich_official/20"


def test_post_url_from_alljson_id():
    assert post_url("O_Arestovich_official_7780") == "https://t.me/O_Arestovich_official/7780"
