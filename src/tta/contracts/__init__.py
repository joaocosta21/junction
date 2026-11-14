"""Shared models and ports: the interface between the packages (AIMO/SPEC.md sections 2 to 9).

Only the orchestrator of the build edits this package. Every model is frozen; money and
quantities are `Decimal` and leave the system as JSON numbers.
"""
