from continuum.core.ontology import Ontology

SOFTWARE_ONTOLOGY = Ontology(
    name="software",
    label_extensions=(
        "Commit",
        "Dependency",
        "Service",
        "Deployment",
        "Configuration",
        "Metric",
        "Incident",
    ),
)
