"""AttackBench runner (§10): executes every scenario in a fresh, isolated
tenant against the real firewall and computes honest metrics from the results."""
from __future__ import annotations

from datetime import timedelta

from intentguard.attackbench.families import FAMILIES, INTENT_TEXT
from intentguard.attackbench.metrics import build_report
from intentguard.attackbench.schema import Scenario, ScenarioResult, StepResult
from intentguard.core.schemas import IntentSpec, PolicyRule, utcnow


def _build_intent(engine, scenario: Scenario, org_id: str, principal_id: str):
    if scenario.intent_spec is not None:
        spec = scenario.intent_spec
        intent = IntentSpec(
            org_id=org_id,
            principal_id=principal_id,
            goal=spec.get("goal", "bench_goal"),
            raw_text=spec.get("raw_text", "AttackBench direct spec"),
            allowed_operations=spec.get("allowed_operations", []),
            constraints=spec.get("constraints", []),
            compiled_by="attackbench_spec",
        )
        engine.store.save_intent(intent)
        return intent
    return engine.compile_intent(org_id, principal_id, scenario.intent_text or INTENT_TEXT)


def run_scenario(engine, scenario: Scenario) -> ScenarioResult:
    org = engine.create_organization(f"bench-{scenario.scenario_id}")
    principal = engine.create_principal(org.org_id, "Bench Owner")
    agent = engine.register_agent(org.org_id, principal.principal_id, "bench-agent")
    intent = _build_intent(engine, scenario, org.org_id, principal.principal_id)

    for rule_spec in scenario.policy_rules:
        engine.add_policy_rule(PolicyRule(org_id=org.org_id, **rule_spec))

    session = engine.start_session(org.org_id, agent.agent_id, intent.intent_id)

    if scenario.setup == "expire_capability":
        capability = engine.store.get_capability(org.org_id, session.capability_id)
        capability.expires_at = utcnow() - timedelta(seconds=1)
        engine.store.save_capability(capability)
    elif scenario.setup.startswith("impersonate:"):
        name = scenario.setup.split(":", 1)[1]
        engine.register_agent(org.org_id, principal.principal_id, name)

    step_results: list[StepResult] = []
    latencies: list[float] = []
    for index, step in enumerate(scenario.steps, start=1):
        acting_agent = agent.agent_id
        if scenario.setup.startswith("impersonate:") and index == 1:
            agents = engine.store.list_agents(org.org_id)
            acting_agent = next(a.agent_id for a in agents if a.name == scenario.setup.split(":", 1)[1])
        if scenario.setup == "swap_capability" and index == 1:
            agent_two = engine.register_agent(org.org_id, principal.principal_id, "bench-agent-two")
            session_two = engine.start_session(org.org_id, agent_two.agent_id, intent.intent_id)
            session_two.capability_id = session.capability_id
            engine.store.save_session(session_two)
            session_id, acting_agent = session_two.session_id, agent_two.agent_id
        else:
            session_id = session.session_id

        decision = engine.propose(
            org_id=org.org_id,
            session_id=session_id,
            agent_id=acting_agent,
            tool=step.tool,
            operation=step.operation,
            params=step.params,
        )
        latencies.append(decision.latency_ms)
        step_results.append(StepResult(
            seq=index,
            title=step.title or f"{step.tool}.{step.operation}",
            decision=decision.decision.value,
            reasons=decision.reasons,
            risk_score=decision.risk.score,
        ))
        if decision.decision.value == "allow" and step.execute:
            try:
                engine.execute(org.org_id, decision.decision_id)
            except Exception as exc:  # execution failure is a scenario failure
                return ScenarioResult(
                    scenario_id=scenario.scenario_id, family=scenario.family,
                    benign=scenario.benign, passed=False, expected=scenario.expect,
                    final_decision=decision.decision.value, steps=step_results,
                    failure_reason=f"execution error: {exc}",
                    latencies_ms=latencies,
                )

    final = step_results[-1] if step_results else None
    if final is None:
        passed, failure = False, "no steps executed"
    elif scenario.benign:
        passed = all(s.decision == "allow" for s in step_results)
        failure = "" if passed else "benign scenario was not fully allowed"
    elif scenario.expect == "detected":
        passed = final.decision in {"block", "escalate"}
        failure = "" if passed else "attack was not stopped"
    else:
        passed = final.decision == scenario.expect
        failure = "" if passed else f"expected {scenario.expect}"

    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        family=scenario.family,
        benign=scenario.benign,
        passed=passed,
        expected=scenario.expect,
        final_decision=final.decision if final else "none",
        steps=step_results,
        failure_reason=failure,
        latencies_ms=latencies,
    )


def run_benchmark(engine, org_id: str, max_per_family: int | None = None) -> dict:
    del org_id  # each scenario gets its own tenant for isolation
    scenarios: list[Scenario] = []
    for name, generator in FAMILIES.items():
        scenarios.extend(generator(max_per_family or 10_000))

    results: list[ScenarioResult] = []
    latencies: list[float] = []
    for scenario in scenarios:
        result = run_scenario(engine, scenario)
        results.append(result)
        latencies.extend(result.latencies_ms)

    report = build_report(results, latencies)
    return report.to_dict()
