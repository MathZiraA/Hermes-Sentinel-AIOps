from types import SimpleNamespace as NS

from integrations.hermes_client import _extract_json, fallback_rca, redact
from k8s.watcher import classify_pod
from schemas.events import AgentEvent, Incident, clip_bubble


def _pod(mem_limit=None, **cs):
    status = NS(
        name="pedidos",
        restart_count=cs.get("restarts", 0),
        state=NS(waiting=cs.get("waiting"), terminated=cs.get("term")),
        last_state=NS(terminated=cs.get("last")),
    )
    limits = {"memory": mem_limit} if mem_limit else None
    spec = NS(containers=[NS(name="pedidos", resources=NS(limits=limits))])
    return NS(metadata=NS(namespace="stockflow", name="pedidos-abc"), spec=spec, status=NS(container_statuses=[status]))


def test_classify_oomkilled_wins_over_crashloop():
    pod = _pod(
        waiting=NS(reason="CrashLoopBackOff", message="back-off"),
        last=NS(reason="OOMKilled", exit_code=137),
        restarts=3,
    )
    [d] = classify_pod(pod)
    assert d.type == "OOMKilled" and d.pod == "pedidos-abc"


def test_exit137_with_memory_limit_is_probable_oom():
    # caso real do chaos `relatorios`: o kernel mata o filho do stress, o kubelet reporta Error/137
    pod = _pod(
        mem_limit="64Mi",
        waiting=NS(reason="CrashLoopBackOff", message="back-off"),
        last=NS(reason="Error", exit_code=137),
        restarts=2,
    )
    [d] = classify_pod(pod)
    assert d.type == "OOMKilled" and "64Mi" in d.reason


def test_exit137_without_memory_limit_stays_crashloop():
    pod = _pod(waiting=NS(reason="CrashLoopBackOff", message="back-off"), last=NS(reason="Error", exit_code=137))
    [d] = classify_pod(pod)
    assert d.type == "CrashLoopBackOff"


def test_exit1_with_memory_limit_stays_crashloop():
    pod = _pod(
        mem_limit="256Mi",
        waiting=NS(reason="CrashLoopBackOff", message="back-off"),
        last=NS(reason="Error", exit_code=1),
    )
    [d] = classify_pod(pod)
    assert d.type == "CrashLoopBackOff"


def test_classify_errimagepull_maps_to_imagepullbackoff():
    [d] = classify_pod(_pod(waiting=NS(reason="ErrImagePull", message="not found")))
    assert d.type == "ImagePullBackOff"


def test_healthy_pod_has_no_detection():
    assert classify_pod(_pod()) == []


def test_redact_hides_secrets():
    text = "SPRING_DATASOURCE_PASSWORD=supersecreta jdbc:mysql://root:abc123@mysql:3306/db Authorization: Bearer abcdefghijklmnop1234"
    out = redact(text)
    assert "supersecreta" not in out and "abc123" not in out and "abcdefghijklmnop1234" not in out


def test_bubble_is_clipped_to_90():
    e = AgentEvent(
        agentId="supervisor",
        agentName="Supervisor",
        role="x",
        status="talking",
        targetZone="CENTRAL_HUB",
        bubbleMessage="a" * 200,
    )
    assert len(e.bubbleMessage) == 90
    assert clip_bubble("  oi   tudo  ") == "oi tudo"


def test_extract_json_from_fenced_answer():
    assert _extract_json('bla ```json\n{"rootCause": "x"}\n``` fim') == {"rootCause": "x"}


def test_fallback_rca_is_complete():
    inc = Incident(
        id="INC-1",
        type="OOMKilled",
        namespace="stockflow",
        pod="p",
        deployment="pedidos",
        reason="exit 137",
        logs="java.lang.OutOfMemoryError: Java heap space",
    )
    rca = fallback_rca(inc, [("OOMKilled.md", "...")], "teste")
    assert rca["source"] == "fallback" and rca["recommendedAction"]["type"] == "rollout_restart"
    assert len(rca["stakeholderSummary"]) <= 90 and rca["runbooks"] == ["OOMKilled.md"]
