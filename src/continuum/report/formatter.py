from __future__ import annotations

from datetime import datetime

from continuum.report.model import InvestigationReport


class ReportFormatter:
    """Pure text formatter for the deterministic M11 report model."""

    def format(
        self,
        report: InvestigationReport,
    ) -> str:
        if not isinstance(report, InvestigationReport):
            raise TypeError("report must be an InvestigationReport")

        return "\n".join(
            [
                "QUESTION",
                report.question,
                "",
                "MOST SUPPORTED EXPLANATION",
                self._verdict_and_explanation(report),
                "",
                "EVIDENCE PATH",
                self._paths(report),
                "",
                "OBSERVED FACTS",
                self._statements(report.observed_facts),
                "",
                "DERIVED RELATIONSHIPS",
                self._statements(report.derived_relationships),
                "",
                "SUPPORTED INFERENCES",
                self._statements(report.supported_inferences),
                "",
                "CONTRADICTIONS",
                self._items(report.contradictions),
                "",
                "UNKNOWN / EVIDENCE GAPS",
                self._items(report.unknowns),
                "",
                "SOURCES",
                self._sources(report),
                "",
                "INVESTIGATION TRACE",
                self._items(report.investigation_trace),
            ]
        )

    @staticmethod
    def _verdict_and_explanation(
        report: InvestigationReport,
    ) -> str:
        return f"{report.verdict}\n{report.most_supported_explanation}"

    @staticmethod
    def _paths(
        report: InvestigationReport,
    ) -> str:
        if not report.evidence_path:
            return "No candidate path is present in the investigation state."

        blocks = []

        for path in report.evidence_path:
            lines = [
                (f"[{path.path_id}] {path.temporal_status}: {path.temporal_reason}")
            ]

            for index, node in enumerate(path.node_ids):
                lines.append(node)

                if index < len(path.relationships):
                    lines.append(f"  ↓ {path.relationships[index]}")

            if path.evidence_ids:
                lines.append("  evidence: " + ", ".join(path.evidence_ids))
            else:
                lines.append("  evidence: none")

            blocks.append("\n".join(lines))

        return "\n\n".join(blocks)

    @staticmethod
    def _statements(
        statements,
    ) -> str:
        if not statements:
            return "None recorded."

        lines = []

        for item in statements:
            refs = []

            if item.evidence_ids:
                refs.append("evidence=" + ",".join(item.evidence_ids))

            if item.path_ids:
                refs.append("paths=" + ",".join(item.path_ids))

            if item.hypothesis_ids:
                refs.append("hypotheses=" + ",".join(item.hypothesis_ids))

            suffix = f" [{'; '.join(refs)}]" if refs else ""

            lines.append(f"- {item.text}{suffix}")

        return "\n".join(lines)

    @staticmethod
    def _items(
        items,
    ) -> str:
        if not items:
            return "None recorded."

        return "\n".join(f"- {item}" for item in items)

    @staticmethod
    def _sources(
        report: InvestigationReport,
    ) -> str:
        if not report.sources:
            return "None recorded."

        lines = []

        for source in report.sources:
            detail = f"- {source.id} — {source.name} — {source.status}"

            if source.record:
                detail += f" — record={source.record}"

            if source.span:
                detail += f" — span={source.span}"

            if source.observed_at:
                observed_at = (
                    source.observed_at.isoformat()
                    if isinstance(source.observed_at, datetime)
                    else source.observed_at
                )

                detail += (
                    " — observed_at="
                    + observed_at
                )

            lines.append(detail)

        return "\n".join(lines)


def format_report(
    report: InvestigationReport,
) -> str:
    return ReportFormatter().format(report)
