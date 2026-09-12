"""Fail-closed errors raised by the Lead Generator kernel."""


class LeadGeneratorKernelError(RuntimeError):
    """Base class for modular runtime failures safe to expose without secrets."""


class PluginManifestError(LeadGeneratorKernelError):
    """A plugin manifest or its configuration is invalid."""


class CompositionError(LeadGeneratorKernelError):
    """The requested plugin graph cannot be composed safely."""


class CustomizationError(LeadGeneratorKernelError):
    """A private customization cannot be previewed or applied safely."""
