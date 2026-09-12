"""Non-replaceable authorization boundary for sensitive plugin actions."""

from __future__ import annotations

from leadgenerator.kernel.contracts import ActionDescriptor
from leadgenerator.kernel.errors import LeadGeneratorKernelError


class ApprovalRequired(LeadGeneratorKernelError):
    """A sensitive action was attempted without point-of-action approval."""


class ApprovalPolicy:
    """Enforce effects on the server even when an interface is replaced."""

    def authorize(self, action: ActionDescriptor, *, confirmed: bool = False) -> None:
        if not action.enabled:
            raise ApprovalRequired(action.disabled_reason or "Action unavailable.")
        if action.effect in {"paid_read", "external_write"} and not confirmed:
            raise ApprovalRequired(
                "Cette action exige une confirmation humaine explicite au point "
                "d'exécution."
            )
