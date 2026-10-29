from continuum.core.ontology import Ontology

SUPPLY_CHAIN_ONTOLOGY = Ontology(
    name="supply-chain",
    label_extensions=(
        "Supplier",
        "Component",
        "Factory",
        "Shipment",
        "Warehouse",
        "Customer",
        "Impact",
    ),
)
