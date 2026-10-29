from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

THEME = Theme(
    {
        "continuum.title": "bold cyan",
        "continuum.subtitle": "dim",
        "continuum.pass": "bold green",
        "continuum.fail": "bold red",
        "continuum.value": "white",
        "continuum.label": "bold",
    }
)

console = Console(theme=THEME, highlight=False)


@dataclass(frozen=True)
class CheckResult:
    name: str
    detail: str = ""


def header(milestone: str, title: str) -> None:
    console.print(
        Panel(
            Text.assemble(
                ("CONTINUUM", "bold white"),
                ("  ·  ", "dim"),
                (milestone, "continuum.title"),
                ("\n", ""),
                (title, "continuum.subtitle"),
            ),
            border_style="cyan",
            padding=(1, 2),
        )
    )


def checks(results: Iterable[CheckResult]) -> None:
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 1),
        expand=False,
    )

    table.add_column("status", width=3, justify="center")
    table.add_column("check", style="continuum.label", no_wrap=True)
    table.add_column("detail", style="continuum.value")

    for result in results:
        table.add_row("✓", result.name, result.detail)

    console.print(table)


def success(milestone: str) -> None:
    console.print()
    console.print(
        Panel(
            Text(f"{milestone} STATUS: PASS", style="continuum.pass"),
            border_style="green",
            padding=(0, 2),
        )
    )


def failure(message: str) -> None:
    console.print()
    console.print(
        Panel(
            Text(message, style="continuum.fail"),
            title="CONTINUUM · CHECK FAILED",
            border_style="red",
            padding=(1, 2),
        )
    )


def info(label: str, value: str) -> None:
    console.print(
        f"  [continuum.label]{label}[/continuum.label] "
        f"[continuum.value]{value}[/continuum.value]"
    )


def section(title: str) -> None:
    console.print()
    console.rule(
        f"[continuum.title]{title}[/continuum.title]",
        style="cyan",
    )


def path(nodes: list[str], relationships: list[str]) -> None:
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 1),
    )

    table.add_column("step", style="dim", width=5, justify="right")
    table.add_column("node", style="bold white")
    table.add_column("relationship", style="yellow")

    for index, node in enumerate(nodes):
        relationship = relationships[index] if index < len(relationships) else ""

        table.add_row(
            str(index + 1),
            node,
            relationship,
        )

    console.print(table)
