from agents.pack.core.agent import handle

def req(org="org_demo_alpha"):
    return {"schema_version":"1.0","request_id":"WF-org_demo_alpha-UNIT-0001:pack","workflow_id":"WF-org_demo_alpha-UNIT-0001","stage":"pack","subject":{"org_id":org,"subject_id":"UNIT-0001","route":"mfn"},"inputs":[],"previous_evidence":[],"context":{"overrides":[]}}

def test_no_capture_is_uncertain_not_success():
    out=handle(req())
    assert out["verdict"]=="UNCERTAIN"
    assert out["status"]=="pending"

def test_wrong_tenant_rejected():
    try:
        handle(req("org_demo_bravo"))
    except LookupError:
        return
    raise AssertionError("wrong tenant was accepted")
