"""Stable contracts and composition runtime for modular Lead Generator plugins."""

from leadgenerator.kernel.composition import (
    LEADGENERATOR_KERNEL_VERSION,
    LEADGENERATOR_SDK_VERSION,
    LeadGeneratorRuntime,
    get_runtime,
)

__all__ = [
    "LEADGENERATOR_KERNEL_VERSION",
    "LEADGENERATOR_SDK_VERSION",
    "LeadGeneratorRuntime",
    "get_runtime",
]
