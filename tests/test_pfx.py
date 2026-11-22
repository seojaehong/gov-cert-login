import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import list_certs  # noqa: E402


def test_pfx_in_extra_dir_listed_with_file(tmp_path, monkeypatch):
    p = tmp_path / "가나다(ab)0001.pfx"
    p.write_bytes(b"x")
    monkeypatch.setattr(list_certs, "DEFAULT", str(tmp_path / "none"))
    monkeypatch.setattr(list_certs, "extra_dirs", lambda: [str(tmp_path)])
    cs = list_certs.certs()
    assert [c["cn"] for c in cs] == ["가나다(ab)0001"]
    assert list_certs.files_of(cs[0]) == [str(p)]


def test_npki_files_default():
    c = {"cn": "x", "dir": "D"}
    assert list_certs.files_of(c) == [os.path.join("D", "signCert.der"), os.path.join("D", "signPri.key")]
