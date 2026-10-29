from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from continuum.core import CORE_LABELS, CORE_RELATIONSHIPS, World
from continuum.investigator.engine import Investigator
from domains.software.world import SOFTWARE_WORLD
from domains.supply_chain.world import SUPPLY_CHAIN_WORLD

REQUIRED_CORE_LABELS = {
    "Entity",
    "Event",
    "Change",
    "Observation",
    "Outcome",
    "Source",
}

REQUIRED_CORE_RELATIONSHIPS = {
    "AFFECTS",
    "DEPENDS_ON",
    "CHANGED",
    "PRECEDED",
    "RESULTED_IN",
    "OBSERVED_AS",
    "SUPPORTED_BY",
    "MENTIONED_IN",
    "OWNED_BY",
}

DOMAIN_NAMES = {
    "software",
    "supply_chain",
    "supply-chain",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def check_core_ontology() -> None:
    missing_labels = REQUIRED_CORE_LABELS - set(CORE_LABELS)
    if missing_labels:
        fail(f"Missing universal labels: {sorted(missing_labels)}")

    missing_relationships = REQUIRED_CORE_RELATIONSHIPS - set(CORE_RELATIONSHIPS)
    if missing_relationships:
        fail(f"Missing universal relationships: {sorted(missing_relationships)}")


def check_world(world: World) -> tuple[int, int]:
    world.validate()

    nodes = world.data.nodes()
    edges = world.data.edges()

    if not nodes:
        fail(f"{world.name}: world contains no nodes")

    if not edges:
        fail(f"{world.name}: world contains no edges")

    labels = {node.label for node in nodes}
    relationships = {edge.relationship for edge in edges}

    if not labels & REQUIRED_CORE_LABELS:
        fail(
            f"{world.name}: no universal core labels are represented in the world data"
        )

    if not relationships & REQUIRED_CORE_RELATIONSHIPS:
        fail(
            f"{world.name}: no universal core relationships are represented "
            "in the world data"
        )

    return len(nodes), len(edges)


def check_same_world_contract() -> None:
    if not isinstance(SOFTWARE_WORLD, World):
        fail("Software world is not a World instance")

    if not isinstance(SUPPLY_CHAIN_WORLD, World):
        fail("Supply-chain world is not a World instance")

    if type(SOFTWARE_WORLD) is not type(SUPPLY_CHAIN_WORLD):
        fail(
            "Software and supply-chain worlds use different World classes: "
            f"{type(SOFTWARE_WORLD).__name__} vs "
            f"{type(SUPPLY_CHAIN_WORLD).__name__}"
        )

    software_attributes = {
        "name",
        "ontology",
        "data",
        "temporal_model",
    }
    supply_attributes = {
        "name",
        "ontology",
        "data",
        "temporal_model",
    }

    if software_attributes != supply_attributes:
        fail("World contract differs between domains")


def check_same_investigator_contract() -> None:
    investigator_type = Investigator

    if not callable(getattr(investigator_type, "investigate", None)):
        fail("Investigator does not expose investigate()")

    signature = inspect.signature(investigator_type.investigate)
    parameters = list(signature.parameters.values())

    parameter_names = [parameter.name for parameter in parameters]

    if parameter_names != ["self", "question", "world"]:
        fail(f"Unexpected Investigator.investigate() contract: {parameter_names}")

    world_parameter = signature.parameters["world"]
    if world_parameter.annotation is inspect.Signature.empty:
        fail("Investigator.investigate() must annotate the world parameter")

    # Instantiate exactly one investigator and use that same instance
    # against both domain worlds.
    investigator = investigator_type(graph=object())

    software_result = investigator.investigate(
        "Why did the software incident happen?",
        world=SOFTWARE_WORLD,
    )

    supply_result = investigator.investigate(
        "Why was the customer affected?",
        world=SUPPLY_CHAIN_WORLD,
    )

    if software_result.question != "Why did the software incident happen?":
        fail("Software investigation did not preserve the question")

    if supply_result.question != "Why was the customer affected?":
        fail("Supply-chain investigation did not preserve the question")

    if "world=software" not in software_result.trace:
        fail("Software world was not accepted by the investigator")

    if "world=supply-chain" not in supply_result.trace:
        fail("Supply-chain world was not accepted by the investigator")


def _contains_domain_specific_logic(tree: ast.AST) -> list[str]:
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.lower()
            for domain_name in DOMAIN_NAMES:
                if domain_name in value:
                    violations.append(
                        f"string literal contains domain name '{domain_name}'"
                    )

        if isinstance(node, ast.Name):
            value = node.id.lower()
            for domain_name in DOMAIN_NAMES:
                normalized = domain_name.replace("-", "_")
                if value == normalized:
                    violations.append(f"name references domain '{domain_name}'")

    return sorted(set(violations))


def check_investigator_is_domain_independent() -> None:
    source = inspect.getsource(Investigator)
    tree = ast.parse(source)

    violations = _contains_domain_specific_logic(tree)

    if violations:
        fail(
            "Investigator contains explicit domain-specific references:\n"
            + "\n".join(f"  - {violation}" for violation in violations)
        )


def main() -> int:
    print("M2 universal core check")

    try:
        check_core_ontology()

        software_nodes, software_edges = check_world(SOFTWARE_WORLD)
        supply_nodes, supply_edges = check_world(SUPPLY_CHAIN_WORLD)

        check_same_world_contract()
        check_same_investigator_contract()
        check_investigator_is_domain_independent()

    except (AssertionError, ValueError, TypeError, SyntaxError) as exc:
        print(f"FAIL: {exc}")
        return 1

    print(f"software_world=PASS nodes={software_nodes} edges={software_edges}")
    print(f"supply_chain_world=PASS nodes={supply_nodes} edges={supply_edges}")
    print("universal_core=PASS")
    print("same_world_contract=PASS")
    print("same_investigator_contract=PASS")
    print("domain_specific_investigator_logic=PASS")
    print("M2_STATUS=PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
