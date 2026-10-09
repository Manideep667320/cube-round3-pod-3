from agents.pack.core.verifier import verify_pack

def test_exact_match():
    r=verify_pack([{"sku":"A","quantity":2}],[{"sku":"A","quantity":2}])
    assert r["pass"]

def test_missing_and_extra():
    r=verify_pack([{"sku":"A","quantity":2}],[{"sku":"A","quantity":1},{"sku":"B","quantity":1}])
    assert not r["pass"]
    assert r["missing"]["a"] == 1
    assert r["extra"]["b"] == 1
