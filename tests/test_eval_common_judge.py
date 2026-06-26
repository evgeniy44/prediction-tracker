from eval_common.judge import fingerprint_prompt, shuffle_options


def test_fingerprint_prompt_deterministic_and_known():
    assert fingerprint_prompt("abc") == fingerprint_prompt("abc")
    assert fingerprint_prompt("abc") != fingerprint_prompt("abd")
    # sha256("abc") = ba7816bf...
    assert fingerprint_prompt("abc").startswith("ba7816bf")


def test_shuffle_options_deterministic_complete_nonmutating():
    opts = ["a", "b", "c", "d", "e"]
    s1 = shuffle_options(opts, seed=42)
    s2 = shuffle_options(opts, seed=42)
    assert s1 == s2  # детерміновано за seed
    assert sorted(s1) == sorted(opts)  # усі опції присутні
    assert opts == ["a", "b", "c", "d", "e"]  # вхід не мутовано
